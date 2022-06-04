import builtins
import dis
import sys
import traceback
import types
import typing
import math
import json
import os

from bytecodemanipulation.CodeOptimiser import optimise_code

from bytecodemanipulation.InstructionMatchers import AbstractInstructionMatcher
from bytecodemanipulation.TransformationHelper import (
    BytecodePatchHelper,
    reconstruct_instruction,
)
from bytecodemanipulation.MutableCodeObject import MutableCodeObject, createInstruction
from bytecodemanipulation.util import JUMP_ABSOLUTE
from bytecodemanipulation.util import JUMP_BACKWARDS
from bytecodemanipulation.util import JUMP_FORWARDS
from bytecodemanipulation.util import Opcodes, OPCODE_DATA
from bytecodemanipulation.util import UNCONDITIONAL_JUMPS

# Check, and jump and pop only when check passes
POP_JUMPS = set(getattr(Opcodes, e) for e in OPCODE_DATA.setdefault("control_flow", {}).setdefault("check_and_jump_pop", []))

# Pop, check, jump
JUMP_POPS = set(getattr(Opcodes, e) for e in OPCODE_DATA.setdefault("control_flow", {}).setdefault("pop_and_check_jump", []))

if sys.version_info.major >= 3 and sys.version_info.minor > 11:
    POP_JUMPS |= {
        Opcodes.POP_JUMP_IF_NONE,
        Opcodes.POP_JUMP_IF_NOT_NONE,
    }


class AbstractBytecodeProcessor:
    """
    Bytecode processor class
    Stuff that works on methods on a high level
    """

    def canBeAppliedOnModified(
        self,
        handler,
        function: MutableCodeObject,
        modifier_list: typing.List["AbstractBytecodeProcessor"],
    ) -> bool:
        return True

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        """
        Applies the bytecode processor to the target
        :param handler: the handler instance
        :param target: the target FunctionPatcher instance
        :param helper: the helper instance, the method is responsible for invoking store() on it
        """
        pass

    def is_breaking(self) -> bool:
        return False


class ReplacementProcessor(AbstractBytecodeProcessor):
    def __init__(self, replacement: types.FunctionType):
        self.replacement = replacement

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        target.overrideFrom(MutableCodeObject.from_function(self.replacement))

    def is_breaking(self) -> bool:
        return True


class ConstantReplacer(AbstractBytecodeProcessor):
    def __init__(
        self,
        before,
        after,
        fail_on_not_found=False,
        matcher: AbstractInstructionMatcher = None,
    ):
        self.before = before
        self.after = after
        self.fail_on_not_found = fail_on_not_found
        self.matcher = matcher

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        if self.before not in target.constants:
            if self.fail_on_not_found:
                raise RuntimeError(
                    f"constant {self.before} not found in target {target} (to be replaced with {self.after})"
                )
            return

        helper.replaceConstant(
            self.before,
            self.after,
            matcher=self.matcher.matches if self.matcher is not None else None,
        )
        helper.store()

    def __repr__(self):
        return f"ConstantReplacer(before={self.before}, after={self.after}, matcher={self.matcher})"


class Global2ConstReplace(AbstractBytecodeProcessor):
    def __init__(
        self, global_name: str, after, matcher: AbstractInstructionMatcher = None
    ):
        self.global_name = global_name
        self.after = after
        self.matcher = matcher

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        match = -1
        for index, instruction in helper.getLoadGlobalsLoading(self.global_name):
            match += 1

            if self.matcher is not None and not self.matcher.matches(
                helper, index, match
            ):
                continue

            helper.instruction_listing[index] = target.createLoadConst(self.after)

        helper.store()

    def __repr__(self):
        return f"Global2ConstReplace(global_name='{self.global_name}', after={self.after}, matcher={self.matcher})"


class Attribute2ConstReplace(AbstractBytecodeProcessor):
    def __init__(
        self,
        attr_name: str,
        after,
        matcher: AbstractInstructionMatcher = None,
        load_from_local_hint: str = None,
    ):
        self.attr_name = attr_name
        self.after = after
        self.matcher = matcher
        self.load_from_local_hint = load_from_local_hint

    def __repr__(self):
        return f"Attribute2ConstReplace(attr_name='{self.attr_name}', after={self.after}, matcher={self.matcher})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        match = -1
        # helper.print_stats()
        for index, instr in helper.walk():
            if instr.opcode != Opcodes.LOAD_ATTR:
                continue

            if self.load_from_local_hint is not None:
                source = next(helper.findSourceOfStackIndex(index, 0))
                if source.opcode == Opcodes.LOAD_FAST:
                    assert isinstance(source.argval, str), source.argval

                    if source.argval != self.load_from_local_hint:
                        continue

                else:
                    continue

            match += 1

            if self.matcher is not None and not self.matcher.matches(
                helper, index, match
            ):
                continue

            # We have a <TOS>.<arg> instruction, and want a POP_TOP followed by a LOAD_CONST

            helper.instruction_listing[index] = createInstruction("POP_TOP")
            helper.insertRegion(
                index + 1,
                [helper.patcher.createLoadConst(self.after)],
            )

        helper.store()


class Local2ConstReplace(AbstractBytecodeProcessor):
    def __init__(
        self, local_name: str, after, matcher: AbstractInstructionMatcher = None
    ):
        self.local_name = local_name
        self.after = after
        self.matcher = matcher

    def __repr__(self):
        return f"Local2ConstReplace(local_name='{self.local_name}', after={self.after}, matcher={self.matcher})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        match = -1
        for index, instruction in enumerate(helper.instruction_listing):
            if instruction.opname != "LOAD_FAST":
                continue
            if helper.patcher.variable_names[instruction.arg] != self.local_name:
                continue

            match += 1

            if self.matcher is not None and not self.matcher.matches(
                helper, index, match
            ):
                continue

            helper.instruction_listing[index] = target.createLoadConst(self.after)

        helper.store()


class GlobalReTargetProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        previous_global: str,
        new_global: str,
        matcher: AbstractInstructionMatcher = None,
    ):
        self.previous_global = previous_global
        self.new_global = new_global
        self.matcher = matcher

    def __repr__(self):
        return f"GlobalReTargetProcessor(previous_global='{self.previous_global}', new_global='{self.new_global}', matcher={self.matcher})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        match = -1
        for index, instruction in helper.getLoadGlobalsLoading(self.previous_global):
            match += 1

            if self.matcher is not None and not self.matcher.matches(
                helper, index, match
            ):
                continue

            helper.instruction_listing[index] = target.createLoadGlobal(self.new_global)

        helper.store()


class InjectFunctionCallAtHeadProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        target_func: typing.Callable,
        *args,
        collected_locals=tuple(),
        inline=False,
    ):
        self.target_func = target_func
        self.args = args
        self.collected_locals = collected_locals
        self.inline = inline

        if inline:
            assert (
                len(collected_locals) == 0
            ), "cannot inline when collecting local variables"

    def __repr__(self):
        return f"InjectFunctionCallAtHeadProcessor(target={self.target_func}, args={self.args}, locals={self.collected_locals}, inline={self.inline})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        index = (
            0
            if helper.instruction_listing[0].opname not in ("GEN_START", "RESUME")
            else 1
        )

        if not self.inline:
            helper.insertGivenMethodCallAt(
                index,
                self.target_func,
                *self.args,
                collected_locals=self.collected_locals,
            )
        else:
            # todo: can we inline somehow the arg values?
            helper.insertMethodAt(
                index,
                self.target_func,
            )

        helper.store()


class InjectFunctionCallAtReturnProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        target_func: typing.Callable,
        *args,
        matcher: AbstractInstructionMatcher = None,
        collected_locals=tuple(),
        add_return_value=False,
        inline=False,
    ):
        self.target_func = target_func
        self.args = args
        self.matcher = matcher
        self.collected_locals = collected_locals
        self.add_return_value = add_return_value
        self.inline = inline

        if inline:
            assert (
                len(collected_locals) == 0
            ), "cannot inline when collecting local variables"

    def __repr__(self):
        return f"InjectFunctionCallAtReturnProcessor(target_func={self.target_func}, args={self.args}, matcher={self.matcher}, locals={self.collected_locals}, add_return_value={self.add_return_value}, inline={self.inline})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        matches = -1
        for index, instr in enumerate(helper.instruction_listing):
            if instr.opname == "RETURN_VALUE":
                matches += 1

                if self.matcher is not None and not self.matcher.matches(
                    helper, index, matches
                ):
                    continue

                if not self.inline:
                    helper.insertGivenMethodCallAt(
                        index - 1 if not self.add_return_value else index,
                        self.target_func,
                        *self.args,
                        collected_locals=self.collected_locals,
                        include_stack_top_copy=self.add_return_value,
                    )
                else:
                    helper.insertMethodAt(
                        index - 1 if not self.add_return_value else index,
                        self.target_func,
                    )

        helper.store()


class InjectFunctionCallAtReturnReplaceValueProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        target_func: typing.Callable,
        *args,
        matcher: AbstractInstructionMatcher = None,
        collected_locals=tuple(),
        add_return_value=False,
    ):
        self.target_func = target_func
        self.args = args
        self.matcher = matcher
        self.collected_locals = collected_locals
        self.add_return_value = add_return_value

    def __repr__(self):
        return f"InjectFunctionCallAtReturnReplaceValueProcessor(target_func={self.target_func}, args={self.args}, matcher={self.matcher}, locals={self.collected_locals}, add_return_value={self.add_return_value})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        matches = -1
        for index, instr in enumerate(helper.instruction_listing):
            if instr.opname == "RETURN_VALUE":
                matches += 1

                if self.matcher is not None and not self.matcher.matches(
                    helper, index, matches
                ):
                    continue

                helper.insertRegion(
                    index,
                    [createInstruction("POP_TOP")],
                )
                helper.insertGivenMethodCallAt(
                    index + 1,
                    self.target_func,
                    *self.args,
                    collected_locals=self.collected_locals,
                    pop_result=False,
                    include_stack_top_copy=self.add_return_value,
                )

        helper.store()


class InjectFunctionCallAtYieldProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        target_func: typing.Callable,
        *args,
        matcher: AbstractInstructionMatcher = None,
        collected_locals=tuple(),
        add_yield_value=False,
        inline=False,
    ):
        self.target_func = target_func
        self.args = args
        self.matcher = matcher
        self.collected_locals = collected_locals
        self.add_yield_value = add_yield_value
        self.inline = inline

        if inline:
            assert (
                len(collected_locals) == 0
            ), "cannot inline when collecting local variables"

    def __repr__(self):
        return f"InjectFunctionCallAtYieldProcessor(target_func={self.target_func}, args={self.args}, matcher={self.matcher}, locals={self.collected_locals}, add_return_value={self.add_yield_value}, inline={self.inline})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        matches = -1
        for index, instr in enumerate(helper.instruction_listing):
            if instr.opname == "YIELD_VALUE" or instr.opname == "YIELD_FROM":
                matches += 1

                if self.matcher is not None and not self.matcher.matches(
                    helper, index, matches
                ):
                    continue

                if not self.inline:
                    helper.insertGivenMethodCallAt(
                        index,
                        self.target_func,
                        *(instr.opname == "YIELD_FROM",) + self.args,
                        collected_locals=self.collected_locals,
                        include_stack_top_copy=self.add_yield_value,
                    )
                else:
                    helper.insertMethodAt(
                        index,
                        self.target_func,
                    )

        helper.store()


class InjectFunctionCallAtYieldReplaceValueProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        target_func: typing.Callable,
        *args,
        matcher: AbstractInstructionMatcher = None,
        collected_locals=tuple(),
        add_yield_value=False,
        is_yield_from=False,
    ):
        self.target_func = target_func
        self.args = args
        self.matcher = matcher
        self.collected_locals = collected_locals
        self.add_yield_value = add_yield_value
        self.is_yield_from = is_yield_from

    def __repr__(self):
        return f"InjectFunctionCallAtYieldReplaceValueProcessor(target_func={self.target_func}, args={self.args}, matcher={self.matcher}, locals={self.collected_locals}, add_return_value={self.add_yield_value})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        matches = -1
        for index, instr in enumerate(helper.instruction_listing):
            if instr.opname == "YIELD_VALUE" or instr.opname == "YIELD_FROM":
                matches += 1

                # Do we need to change the instruction type?
                if self.is_yield_from is not None and (
                    self.is_yield_from != instr.opname == "YIELD_FROM"
                ):
                    if self.is_yield_from:
                        helper.instruction_listing[index] = createInstruction(
                            "YIELD_FROM"
                        )
                    else:
                        helper.instruction_listing[index] = createInstruction(
                            "YIELD_VALUE"
                        )

                if self.matcher is not None and not self.matcher.matches(
                    helper, index, matches
                ):
                    continue

                helper.insertRegion(
                    index,
                    [createInstruction("POP_TOP")],
                )

                helper.insertGivenMethodCallAt(
                    index + (0 if self.add_yield_value else 1),
                    self.target_func,
                    *(instr.opname == "YIELD_FROM",) + self.args,
                    collected_locals=self.collected_locals,
                    pop_result=False,
                    include_stack_top_copy=self.add_yield_value,
                )

        helper.store()


class InjectFunctionCallAtTailProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        target_func: typing.Callable,
        *args,
        collected_locals=tuple(),
        add_return_value=False,
        inline=False,
    ):
        self.target_func = target_func
        self.args = args
        self.collected_locals = collected_locals
        self.add_return_value = add_return_value
        self.inline = inline

        if inline:
            assert (
                len(collected_locals) == 0
            ), "cannot inline when collecting local variables"

    def __repr__(self):
        return f"InjectFunctionCallAtTailProcessor(target_func={self.target_func}, args={self.args}, locals={self.collected_locals}, add_return_value={self.add_return_value}, inline={self.inline})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        assert (
            helper.instruction_listing[-1].opname == "RETURN_VALUE"
        ), "integrity of function failed!"

        if not self.inline:
            helper.insertGivenMethodCallAt(
                len(helper.instruction_listing) - 1,
                self.target_func,
                *self.args,
                collected_locals=self.collected_locals,
                include_stack_top_copy=self.add_return_value,
            )
        else:
            helper.insertMethodAt(
                len(helper.instruction_listing) - 1,
                self.target_func,
            )

        helper.store()


class InjectFunctionLocalVariableModifier(AbstractBytecodeProcessor):
    def __init__(
        self,
        function: typing.Callable,
        local_variables: typing.List[str],
        matcher: AbstractInstructionMatcher,
        *args,
        collected_locals=tuple(),
    ):
        self.function = function
        self.local_variables = local_variables
        self.args = args
        self.matcher = matcher
        self.collected_locals = collected_locals

    def __repr__(self):
        return f"InjectFunctionLocalVariableModifier(target_func={self.function}, locals={self.collected_locals}, args={self.args}, matcher={self.matcher}, modified_locals={self.local_variables})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        collected_locals = [
            helper.patcher.createLoadFast(e) for e in reversed(self.local_variables)
        ]
        store_locals = [
            createInstruction("UNPACK_SEQUENCE", len(self.local_variables))
        ] + [helper.patcher.createStoreFast(e) for e in reversed(self.local_variables)]

        for index, instruction in enumerate(helper.instruction_listing):
            if self.matcher.matches(helper, index, index):
                helper.insertGivenMethodCallAt(
                    index,
                    self.function,
                    *self.args,
                    collected_locals=self.collected_locals,
                    special_args_collectors=collected_locals,
                    pop_result=False,
                    insert_after=store_locals,
                )

        helper.store()


class MethodInlineProcessor(AbstractBytecodeProcessor):
    def __init__(
        self,
        func_name: str,
        target_accessor: typing.Callable[[], typing.Callable] = None,
        matcher: AbstractInstructionMatcher = None,
    ):
        self.func_name = func_name
        self.target_accessor = target_accessor
        self.matcher = matcher

    def __repr__(self):
        return f"MethodInlineProcessor(func_name={self.func_name}, accessor={self.target_accessor}, matcher={self.matcher})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        matches = 0
        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                # print("looking at ", instr, helper.CALL_FUNCTION_NAME)
                # print(instr.opname == helper.CALL_FUNCTION_NAME, self.func_name)

                if (
                    instr.opname == helper.CALL_FUNCTION_NAME
                    and self.func_name.startswith("%.")
                ):
                    try:
                        source = next(helper.findSourceOfStackIndex(index, instr.arg))

                        # print(source, self.func_name)

                        if source.opcode == Opcodes.LOAD_METHOD:
                            if source.argval == self.func_name.split(".")[-1]:
                                matches += 1
                                if self.matcher and not self.matcher.matches(
                                    helper, index, matches
                                ):
                                    continue

                                if (
                                    helper.instruction_listing[index + 1].opcode
                                    == Opcodes.GET_AWAITABLE
                                ):
                                    helper.instruction_listing[
                                        index + 1
                                    ] = createInstruction("POP_TOP")

                                if self.target_accessor is not None:
                                    helper.deleteInstruction(instr)
                                    index = (
                                        helper.insertMethodAt(
                                            index,
                                            self.target_accessor(),
                                            added_args=instr.arg,
                                            discard_return_result=False,
                                        )
                                        - 1
                                    )
                                    break

                    except ValueError:
                        print(f"during tracing source of {instr}")
                        traceback.print_exc()
                    except:
                        print(f"during tracing source of {instr}")
                        traceback.print_exc()

                elif instr.opname == helper.CALL_FUNCTION_NAME:
                    # print("lookup", index, instr)
                    # helper.print_stats()

                    source = next(helper.findSourceOfStackIndex(index, instr.arg))

                    # print(source, self.func_name, source.opcode == Opcodes.LOAD_DEREF, source.argval == self.func_name)

                    if (
                        source.opcode in (Opcodes.LOAD_DEREF, Opcodes.LOAD_GLOBAL)
                        and source.argval == self.func_name
                    ):
                        matches += 1
                        if self.matcher and not self.matcher.matches(
                            helper, index, matches
                        ):
                            continue

                        if self.target_accessor is not None:
                            method = self.target_accessor()
                            arg_count = instr.arg

                            if (
                                helper.instruction_listing[index + 1].opcode
                                == Opcodes.GET_AWAITABLE
                            ):
                                helper.instruction_listing[
                                    index + 1
                                ] = createInstruction("POP_TOP")

                            # remove the POP_TOP instruction
                            helper.deleteRegion(index, index + 1)

                            index = (
                                helper.insertMethodAt(
                                    index,
                                    method,
                                    added_args=arg_count,
                                    discard_return_result=False,
                                    inter_code=(createInstruction("POP_TOP"),),
                                )
                                - 1
                            )
                            break
                else:
                    break

            helper.store()


class RemoveFlowBranchProcessor(AbstractBytecodeProcessor):
    def __init__(self, matcher: AbstractInstructionMatcher, target_jumped_branch=True):
        self.matcher = matcher
        self.target_jumped_branch = target_jumped_branch

    def __repr__(self):
        return f"RemoveFlowBranchProcessor(matcher={self.matcher}, target_jumped_branch={self.target_jumped_branch})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        match = 0
        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                # Pop, check, jump
                if instr.opcode in JUMP_POPS:
                    if self.modifyAt(helper, index, match):
                        match += 1
                        break

                # check, (jump & pop)
                elif instr.opcode in POP_JUMPS:
                    if self.modifyAt(helper, index, match, pop=self.target_jumped_branch):
                        match += 1
                        break
            else:
                break

        helper.store()

    def modifyAt(self, helper: BytecodePatchHelper, index: int, match: int, pop=True):
        instr = helper.instruction_listing[index]

        if not self.matcher or self.matcher.matches(helper, index, match):
            helper.instruction_listing[index] = createInstruction(
                "POP_TOP" if pop else "NOP"
            )

            if self.target_jumped_branch:
                if instr.opcode in JUMP_ABSOLUTE:
                    # In python 3.11, there are two absolute jumps, but no unconditional variant, so we need
                    # to use a JUMP_FORWARD instruction  todo: use also JUMP_BACKWARD
                    if UNCONDITIONAL_JUMPS[0] is None:
                        helper.insertRegion(
                            index + 1, [createInstruction(UNCONDITIONAL_JUMPS[1], instr.arg + 1 - index)]
                        )

                    else:
                        helper.insertRegion(
                            index + 1, [createInstruction(UNCONDITIONAL_JUMPS[0], instr.arg + 1)]
                        )

                elif instr.opcode in JUMP_FORWARDS:
                    helper.insertRegion(
                        index + 1, [createInstruction(UNCONDITIONAL_JUMPS[1], instr.arg + 1)]
                    )

                elif instr.opcode in JUMP_BACKWARDS:
                    helper.insertRegion(
                        index + 1, [createInstruction(UNCONDITIONAL_JUMPS[2], instr.arg + 1)]
                    )

                else:
                    raise RuntimeError(instr)

            return True

        return False


class GlobalStaticLookupProcessor(AbstractBytecodeProcessor):
    """
    Processor for transforming LOAD_GLOBAL instructions
    into LOAD_CONST instructions

    todo: add a way to do custom data lookups
    """

    def __init__(
        self, global_name: str = None, matcher: AbstractInstructionMatcher = None
    ):
        self.global_name = global_name
        self.matcher = matcher

    def __repr__(self):
        return f"GlobalStaticLookupProcessor(global_name={self.global_name}, matcher={self.matcher})"

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        matches = 0
        for index, instr in helper.walk():
            if instr.opcode == Opcodes.LOAD_GLOBAL and (
                self.global_name is None or instr.argval == self.global_name
            ):
                matches += 1
                if self.matcher is not None and not self.matcher.matches(
                    helper, index, matches
                ):
                    continue

                try:
                    value = helper.patcher.target.__globals__[instr.argval]
                except KeyError:
                    try:
                        value = globals()[instr.argval]
                    except KeyError:
                        value = eval(instr.argval)

                helper.instruction_listing[index] = helper.patcher.createLoadConst(
                    value
                )

        helper.store()


class SideEffectFreeMethodCallRemover(AbstractBytecodeProcessor):
    """
    Removes calls to function which are side effect free

    Requires the methods to be statically known, by e.g. static builtins
    """

    SIDE_EFFECT_FREE_BUILTINS = {
        min,
        max,
        range,
    }

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1

            for index, instr in list(helper.walk())[index:-2]:
                if instr.opcode == Opcodes.CALL_FUNCTION and helper.instruction_listing[index + 1].opcode == Opcodes.POP_TOP:
                    target = next(helper.findSourceOfStackIndex(index, instr.arg))

                    if target.opcode == Opcodes.LOAD_CONST:
                        target = target.argval

                        if target in self.SIDE_EFFECT_FREE_BUILTINS or ("optimiser_container" in target.__dict__ and target.optimiser_container.is_side_effect_free):
                            helper.deleteRegion(index, index+2)
                            helper.insertRegion(index, [createInstruction("POP_TOP")] * instr.arg)
                            index -= instr.arg - 2
                            break

            else:
                break

        helper.store()


class EvalAtOptimisationTime(AbstractBytecodeProcessor):
    """
    Helper for evaluating values at optimisation time

    Require calls to be eval to be already constant functions with constant parameters
    todo: run some normal optimisation beforehand so this can do more
    """

    OPTIMISATION_TIME_STABLE_BUILTINS = set()
    STATIC_REF_MODULES = {}

    @classmethod
    def init_const_expr(cls):
        with open(
                f"{os.path.dirname(__file__)}/data/py{sys.version_info.major}.{sys.version_info.minor}_const_expressions.json") as f:
            data = json.load(f)

        # todo: make data-driven
        cls.OPTIMISATION_TIME_STABLE_BUILTINS |= {
            getattr(builtins, e) for e in data.setdefault("builtins", [])
        }

        for entry in data.setdefault("std_library", []):
            module = __import__(entry["name"])
            cls.STATIC_REF_MODULES[entry["name"]] = module

            cls.OPTIMISATION_TIME_STABLE_BUILTINS |= {
                getattr(module, e) for e in entry["items"] if hasattr(module, e)
            }

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        optimise_code(helper)

        while True:
            for index, instr in helper.walk():
                if instr.opcode == Opcodes.CALL_FUNCTION:
                    target = target_opcode = next(helper.findSourceOfStackIndex(index, instr.arg))

                    if target.opcode == Opcodes.LOAD_CONST:
                        target = target.argval

                        if target in self.OPTIMISATION_TIME_STABLE_BUILTINS or (hasattr(target, "__dict__") and "optimiser_container" in target.__dict__ and target.optimiser_container.is_side_effect_free):
                            args = [next(helper.findSourceOfStackIndex(index, i)) for i in range(instr.arg - 1, -1, -1)]

                            # todo: can we do more in other cases?
                            if all(ins.opcode == Opcodes.LOAD_CONST for ins in args):
                                value = target(*(e.argval for e in args))

                                helper.instruction_listing[index] = helper.patcher.createLoadConst(value)

                                for ins in args:
                                    helper.instruction_listing[ins.offset // 2] = createInstruction("NOP")

                                helper.instruction_listing[target_opcode.offset // 2] = createInstruction("NOP")
                                break

                elif instr.opcode == Opcodes.CALL_FUNCTION_KW:
                    target = target_opcode = next(helper.findSourceOfStackIndex(index, instr.arg + 1))
                    kw_source = next(helper.findSourceOfStackIndex(index, 0))

                    if target.opcode == kw_source.opcode == Opcodes.LOAD_CONST:
                        target = target.argval
                        kw_args = kw_source.argval

                        if target in self.OPTIMISATION_TIME_STABLE_BUILTINS or (hasattr(target, "__dict__") and "optimiser_container" in target.__dict__ and target.optimiser_container.is_side_effect_free):
                            args = [next(helper.findSourceOfStackIndex(index, i)) for i in range(instr.arg, 0, -1)]

                            # todo: can we do more in other cases?
                            if all(ins.opcode == Opcodes.LOAD_CONST for ins in args):
                                value = target(*(e.argval for e in args[:(len(args)-len(kw_args))]), **{key: args[len(kw_args)+i].argval for i, key in enumerate(kw_args)})

                                helper.instruction_listing[index] = helper.patcher.createLoadConst(value)

                                for ins in args:
                                    helper.instruction_listing[ins.offset // 2] = createInstruction("NOP")

                                helper.instruction_listing[kw_source.offset // 2] = createInstruction("NOP")
                                helper.instruction_listing[target_opcode.offset // 2] = createInstruction("NOP")
                                break

            else:
                break

        helper.store()


EvalAtOptimisationTime.init_const_expr()


class StandardLibraryResolver(AbstractBytecodeProcessor):
    def __init__(self, resolve: str):
        self.resolve = resolve

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        library = __import__(self.resolve)

        for index, instr in helper.walk():
            if instr.opcode == Opcodes.LOAD_GLOBAL and instr.argval == self.resolve:
                helper.instruction_listing[index] = helper.patcher.createLoadConst(library)

        helper.store()


import math, os, json, collections


class StandardLibraryAllResolver(AbstractBytecodeProcessor):
    STANDARD_MODULE_NAMES = EvalAtOptimisationTime.STATIC_REF_MODULES

    def __init__(self, do_module_scope_lookup=True):
        self.do_module_scope_lookup = do_module_scope_lookup

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        if self.do_module_scope_lookup:
            imported_modules = set()

            for index, instr in helper.walk():
                if instr.opcode == Opcodes.LOAD_GLOBAL and instr.argval in target.target.__globals__:
                    module = target.target.__globals__[instr.argval]
                    if module.__name__ in self.STANDARD_MODULE_NAMES and self.STANDARD_MODULE_NAMES[module.__name__] == module:
                        imported_modules.add(module.__name__)

        else:
            imported_modules = self.STANDARD_MODULE_NAMES

        for index, instr in helper.walk():
            if instr.opcode == Opcodes.LOAD_GLOBAL and instr.argval in imported_modules:
                helper.instruction_listing[index] = helper.patcher.createLoadConst(self.STANDARD_MODULE_NAMES[instr.argval])

                if helper.instruction_listing[index + 1].opcode == Opcodes.LOAD_METHOD:
                    helper.instruction_listing[index + 1] = createInstruction("LOAD_ATTR", helper.instruction_listing[index + 1].arg)

        helper.store()


class StaticObjectAccessorResolver(AbstractBytecodeProcessor):
    ALL_CHILDREN_OF = set(EvalAtOptimisationTime.STATIC_REF_MODULES.values())
    SPECIFIC_CHILDREN_OF = {}

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: BytecodePatchHelper,
    ):
        for index, instr in helper.walk():
            if instr.opcode == Opcodes.LOAD_ATTR:
                source = next(helper.findSourceOfStackIndex(index, 0))

                if source.opcode == Opcodes.LOAD_CONST:
                    if source.argval in self.ALL_CHILDREN_OF:
                        func_usage = next(helper.findTargetOfStackIndex(index, 0))

                        if func_usage.opcode == Opcodes.CALL_METHOD:
                            helper.instruction_listing[func_usage.offset // 2] = createInstruction("CALL_FUNCTION", func_usage.arg)

                        helper.instruction_listing[index] = helper.patcher.createLoadConst(getattr(source.argval, instr.argval))
                        helper.insertRegion(index, [createInstruction("POP_TOP")])

        helper.store()

