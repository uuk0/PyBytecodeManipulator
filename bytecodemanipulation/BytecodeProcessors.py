import dis
import sys
import traceback
import types
import typing

from bytecodemanipulation.InstructionMatchers import AbstractInstructionMatcher
from bytecodemanipulation.TransformationHelper import (
    MixinPatchHelper,
    reconstruct_instruction,
)
from bytecodemanipulation.MutableCodeObject import MutableCodeObject, createInstruction
from bytecodemanipulation.util import Opcodes


POP_JUMPS = {
    Opcodes.POP_JUMP_IF_FALSE,
    Opcodes.POP_JUMP_IF_TRUE,
}

if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
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
        helper: MixinPatchHelper,
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
        helper: MixinPatchHelper,
    ):
        target.overrideFrom(MutableCodeObject(self.replacement))

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
        helper: MixinPatchHelper,
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
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
    ):
        match = -1
        for index, instr in helper.walk():
            if instr.opcode != Opcodes.LOAD_ATTR:
                continue

            if self.load_from_local_hint is not None:
                source = next(helper.findSourceOfStackIndex(index, 0))
                if source.opcode == Opcodes.LOAD_FAST:
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
    ):
        index = 0 if helper.instruction_listing[0].opname != "GEN_START" else 1

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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
    ):
        matches = 0
        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                if instr.opname == "CALL_METHOD" and self.func_name.startswith("%."):
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
                        pass
                    except:
                        print(f"during tracing source of {instr}")
                        traceback.print_exc()

                elif instr.opcode == Opcodes.CALL_FUNCTION:
                    # print("lookup", index, instr)
                    # helper.print_stats()

                    source = next(helper.findSourceOfStackIndex(index, instr.arg))

                    # print(source, self.func_name, source.opcode == PyOpcodes.LOAD_DEREF, source.argval == self.func_name)

                    if (
                        source.opcode == Opcodes.LOAD_DEREF
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

    def apply(
        self,
        handler,
        target: MutableCodeObject,
        helper: MixinPatchHelper,
    ):
        match = 0
        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                if instr.opcode in {
                    Opcodes.JUMP_IF_FALSE_OR_POP,
                    Opcodes.JUMP_IF_TRUE_OR_POP,
                }:
                    if self.modifyAt(
                        helper, index, match, pop=self.target_jumped_branch
                    ):
                        match += 1
                        break

                elif instr.opcode in POP_JUMPS:
                    if self.modifyAt(helper, index, match):
                        match += 1
                        break
            else:
                break

        helper.store()

    def modifyAt(self, helper: MixinPatchHelper, index: int, match: int, pop=True):
        instr = helper.instruction_listing[index]

        if not self.matcher or self.matcher.matches(helper, index, match):
            helper.instruction_listing[index] = createInstruction(
                "POP_TOP" if pop else "NOP"
            )

            if self.target_jumped_branch:
                if instr.opcode in dis.hasjabs:
                    helper.insertRegion(
                        index + 1, [createInstruction("JUMP_ABSOLUTE", instr.arg + 1)]
                    )
                else:
                    helper.insertRegion(
                        index + 1, [createInstruction("JUMP_RELATIVE", instr.arg)]
                    )

            return True

        return False
