import dis
import inspect
import sys
import traceback
import types
import typing

from bytecodemanipulation.MutableCodeObject import MutableCodeObject, createInstruction
from .util import OPCODE_DATA

from .util import Opcodes, JUMP_ABSOLUTE, JUMP_FORWARDS, JUMP_BACKWARDS
from .util import UNCONDITIONAL_JUMPS


def reconstruct_instruction(
    instr: dis.Instruction,
    arg=None,
    arg_value=None,
    arg_repr=None,
    offset=None,
    jump_target=None,
):
    return dis.Instruction(
        instr.opname,
        instr.opcode,
        arg if arg is not None else instr.arg,
        arg_value if arg_value is not None else instr.argval,
        arg_repr if arg_repr is not None else instr.argrepr,
        offset if offset is not None else instr.offset,
        instr.starts_line,
        jump_target if jump_target is not None else instr.is_jump_target,
    )


def injected_return(value=None):
    """
    Invoke before a normal return in a injected code object to return the method injected into
    This method call and the return will be combined into a regular return statement

    Use from <...>.TransformationHelper import injected_return outside the method in a global scope when possible,
    it makes it easier to detect inside the bytecode

    todo: use this for real!
    """


def capture_local(name: str):
    """
    Captures the value from an outer local variable into this function body.
    Use only in injected (real injection) code!

    WARNING: when storing the result in a local variable, the name of the variable is captured
    in the whole function, meaning any read/write to this name will be redirected to the real local
    variable; This can result in unwanted side effects

    :param name: the name of the local
    :return: the local value
    """


def capture_local_static(name: str):
    """
    Similar to capture_local(name), but will capture only the value ones, and do no permanent binding
    """


# todo: add a way to capture free variables
# todo: add a way to capture global variables
# todo: add a way to capture cell variables

DO_NOTHING = set(getattr(Opcodes, e) for e in OPCODE_DATA.setdefault("stack_effects", {}).setdefault("do_nothing", []))
LOAD_SINGLE_VALUE = set(getattr(Opcodes, e) for e in OPCODE_DATA["stack_effects"].setdefault("load_single", []))
POP_SINGLE_VALUE = set(getattr(Opcodes, e) for e in OPCODE_DATA["stack_effects"].setdefault("pop_single", []))
POP_DOUBLE_VALUE = set(getattr(Opcodes, e) for e in OPCODE_DATA["stack_effects"].setdefault("pop_double", []))
POP_DOUBLE_AND_PUSH_SINGLE = set(getattr(Opcodes, e) for e in OPCODE_DATA["stack_effects"].setdefault("pop_double_and_push_single", []))
POP_SINGLE_AND_PUSH_SINGLE = set(getattr(Opcodes, e) for e in OPCODE_DATA["stack_effects"].setdefault("pop_single_and_push_single", []))


if sys.version_info.major <= 3 and sys.version_info.minor < 11:
    METHOD_CALL = {Opcodes.CALL_METHOD, Opcodes.CALL_FUNCTION}
else:
    METHOD_CALL = Opcodes.CALL


def rebind_instruction_from_insert(instr: dis.Instruction, new_index: int, new_size: int):
    if instr.opcode in JUMP_FORWARDS:
        offset = instr.arg

        if offset + instr.offset >= new_index >= instr.offset:
            offset += new_size
        elif offset + instr.offset < new_index <= instr.offset:
            offset -= new_size

        return reconstruct_instruction(
            instr, arg=offset
        )

    # todo: is this correct?
    elif instr.opcode in JUMP_BACKWARDS:
        offset = instr.arg

        if instr.offset >= new_index >= instr.offset - offset:
            offset += new_size
        elif instr.offset < new_index <= instr.offset - offset:
            offset -= new_size

        return reconstruct_instruction(
            instr, arg=offset
        )

    elif instr.opcode in JUMP_ABSOLUTE:
        offset = instr.arg

        if offset >= new_index:
            offset -= new_size

        return reconstruct_instruction(
            instr, arg=offset,
        )


class BytecodePatchHelper:
    """
    See https://docs.python.org/3/library/dis.html#python-bytecode-instructions for a detailed instruction listing
    Contains helper methods for working with bytecode outside the basic wrapper container

    Can save-ly exchange code regions with others, and redirect jump instructions correctly.

    Also contains code to inline whole methods into the code

    See also https://docs.python.org/3.11/library/inspect.html#code-objects-bit-flags
    """

    def __init__(self, patcher: typing.Union[MutableCodeObject, types.FunctionType]):
        self.patcher = (
            patcher
            if isinstance(patcher, MutableCodeObject)
            else MutableCodeObject.from_function(patcher)
        )
        self.instruction_listing = list(self.patcher.get_instruction_list())

        # todo: this is the wrong lookup; lookup the inspect flag
        self.is_async = self.patcher.flags & inspect.CO_COROUTINE

        self.is_verbose = False

    def enable_verbose_exceptions(self, force=False, verbose_internal_calls=False):
        """
        Helper method for enabling a bytecode emulator on the object;
        Helps when debugging issues, as error messages get more verbose
        (Including times when a normal interpreter would CRASH)

        Will rebind this transformation helper to a new MutableCodeObject instance
        representing the internal method, the one which is going to be debugged, not the
        wrapper code for debugging.

        WARNING: the underlying emulator does currently not support all instructions

        :param force: if to force such a wrapping, even if there is currently one
        :param verbose_internal_calls: if calls in the code to other methods should also be verbose-ed
        """

        if self.is_verbose and not force:
            return
        self.is_verbose = True

        self.store()
        internal = self.patcher.create_method_from()

        # test and test2 are only placeholder constants later replaced by the real values via
        # bytecode manipulation; this removes the need of cellvars/freevars

        def invoke(*args, **kwargs):
            from bytecodemanipulation.Emulator import CURRENT

            return CURRENT.execute(
                "test", *args, invoke_subcalls_via_emulator="test2", **kwargs
            )

        patcher = MutableCodeObject.from_function(invoke)

        # bind the code object as a constant
        patcher.constants[patcher.constants.index("test")] = internal
        patcher.constants[patcher.constants.index("test2")] = verbose_internal_calls

        patcher.free_vars = self.patcher.free_vars
        patcher.cell_vars = self.patcher.cell_vars
        self.patcher.overrideFrom(patcher)
        self.patcher.applyPatches()

        self.patcher = MutableCodeObject.from_function(internal)
        self.instruction_listing = list(self.patcher.get_instruction_list())
        return self

    def walk(self) -> typing.Iterable[typing.Tuple[int, dis.Instruction]]:
        yield from zip(range(len(self.instruction_listing)), self.instruction_listing)

    def store(self):
        self.patcher.instructionList2Code(self.instruction_listing, helper=self)

        try:
            self.instruction_listing[:] = list(self.patcher.get_instruction_list())
        except IndexError:
            print(self.patcher.target)
            print(self.patcher.names)
            print(self.patcher.variable_names)
            print(self.patcher.constants)
            raise

    def re_eval_instructions(self):
        self.store()
        self.instruction_listing[:] = list(self.patcher.get_instruction_list())

    def deleteRegion(
        self, start: int, end: int, safety=True, maps_invalid_to: int = -1
    ):
        """
        Deletes a region from start (including) to end (excluding) of the code, rebinding jumps and similar calls
        outside the region
        If safety is True, will ensure no direct jumps occur into this region
        (This is done during code walking for jump resolving)

        WARNING: the user is required to make sure that stack & variable constraints still hold

        :param start: the start position (including)
        :param end: the end position (excluding)
        :param safety: if to check for instructions jumping INTO the region
        :param maps_invalid_to: an index in the new version where to re-wire jumps to when they would
            lead into the deleted region
        """
        i = 0
        size = end - start

        def rebind_fwd(o: int) -> int:
            nonlocal i

            # Is our jump target IN the region?
            if start <= i + o < end and safety:
                if maps_invalid_to != -1:
                    return maps_invalid_to - i

                raise RuntimeError("Instruction to jump to is getting deleted")

            # If we jump OVER the region
            if i + o >= end and i < start:
                return o - size

            if i + o < start and i >= end:
                return o + size

            return o

        def rebind_bwd(o: int) -> int:
            nonlocal i

            # Is our jump target IN the region?
            if start <= i - o < end and safety:
                if maps_invalid_to != -1:
                    # todo: is this correct?
                    return maps_invalid_to - i

                raise RuntimeError("Instruction to jump to is getting deleted")

            # If we jump OVER the region
            if i - o >= end and i < start:
                return o - size

            if i - o < start and i >= end:
                return o + size

            return o

        def rebind_real(o: int) -> int:
            if start <= o < end and safety:
                if maps_invalid_to != -1:
                    return maps_invalid_to

                raise RuntimeError("Instruction to jump to is getting deleted")

            if o >= end:
                return o - size

            return o

        for i, instr in self.walk():
            if start <= i < end:
                continue

            # Check control flow
            if instr.opcode in JUMP_FORWARDS:
                offset = instr.arg
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_fwd(offset)
                )

            elif instr.opcode in JUMP_BACKWARDS:
                offset = instr.arg
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_bwd(offset)
                )

            elif instr.opcode in JUMP_ABSOLUTE:
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_real(instr.arg)
                )

        del self.instruction_listing[start:end]

    def insertRegion(self, start: int, instructions: typing.List[dis.Instruction]):
        """
        Inserts a list of instructions into the opcode list, resolving the jumps in code correctly

        WARNING: the user is required to make sure that stack & variable constraints still hold

        todo: add variant for adding a single instruction, which can be implemented a lot faster than this stuff

        :param start: where to start the insertion, the first instruction becomes the start index
        :param instructions: list of instructions to insert
        """
        size = len(instructions)

        def rebind_fwd(o: int) -> int:
            nonlocal i

            # If we jump OVER the region
            if i + o >= start > i:
                return o + size

            if i + o < start <= i:
                return o - size

            return o

        def rebind_bwd(o: int) -> int:
            nonlocal i

            # If we jump OVER the region
            if i - o >= start > i:
                return o + size

            if i - o < start <= i:
                return o - size

            return o

        def rebind_real(o: int) -> int:

            # If we jump OVER the region
            if o >= start:
                return o - size

            return o

        for i, instr in self.walk():
            # Check control flow

            if instr.opcode in JUMP_FORWARDS:
                offset = instr.arg
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_fwd(offset)
                )

            elif instr.opcode in JUMP_BACKWARDS:
                offset = instr.arg
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_bwd(offset)
                )

            elif instr.opcode in JUMP_BACKWARDS:
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_real(instr.arg)
                )

        self.instruction_listing = (
            self.instruction_listing[:start]
            + instructions
            + self.instruction_listing[start:]
        )

    def deleteInstruction(self, instr: dis.Instruction):
        self.deleteRegion(instr.offset, instr.offset + 1)
        return self

    def replaceConstant(
        self,
        previous,
        new,
        matcher: typing.Callable[["BytecodePatchHelper", int, int], bool] = None,
    ):
        """
        Replaces a constant with another one
        :param previous: the old constant
        :param new: the new constant
        :param matcher: the matcher for instructions, or None
        """
        if previous not in self.patcher.constants:
            raise ValueError(previous)

        if matcher is None:
            const_index = self.patcher.constants.index(previous)
            self.patcher.constants[const_index] = new
            return
        else:
            const_index = self.patcher.ensureConstant(new)

        match = 0
        for index, instruction in enumerate(self.instruction_listing):
            if instruction.opcode in dis.hasconst:
                match += 1

                if instruction.arg == const_index and (
                    matcher is None or matcher(self, index, match)
                ):
                    self.instruction_listing[index] = dis.Instruction(
                        instruction.opname,
                        instruction.opcode,
                        const_index,
                        new,
                        repr(new),
                        instruction.offset,
                        instruction.starts_line,
                        instruction.is_jump_target,
                    )

    def getLoadGlobalsLoading(
        self, global_name: str
    ) -> typing.Iterable[typing.Tuple[int, dis.Instruction]]:
        for index, instruction in enumerate(self.instruction_listing):
            if (
                instruction.opname == "LOAD_GLOBAL"
                and instruction.argval == global_name
            ):
                yield index, instruction

    def insertMethodAt(
        self,
        start: int,
        method: typing.Union[MutableCodeObject, types.MethodType],
        added_args=0,
        discard_return_result=True,
        inter_code=tuple(),
    ) -> int:
        """
        Inserts a method body at the given position
        Does some magic for linking the code
        Use injected_return() or capture_local() for advance control flow

        Will not modify the passed method. Will copy that object

        All locals not capture()-ed get a new prefix of the method name

        WARNING: injected_return() with arg the arg must be from local variable storage, as it is otherwise
            hard to detect where the method came from (LOAD_GLOBAL somewhere in instruction list...)
        todo: add a better way to trace function calls

        WARNING: highly experimental, it may break at any time!

        todo: for python 3.11, we need to update the target exception table!

        :param start: where the method head should be inserted
        :param method: the method object ot inject
        :param added_args: how many positional args are added to the method call
        :param discard_return_result: if the return result should be deleted or not
        :param inter_code: what code to insert between arg getting and function invoke
        :return: the instruction index at the TAIL of the code
        """

        # We need to transform this object one level up to make things work
        if not isinstance(method, MutableCodeObject):
            method = MutableCodeObject.from_function(method)

        target = method.copy()

        # Rebind all inner local variables to something we cannot possibly enter as code,
        # so we cannot get conflicts (in the normal case)
        # todo: what happens if we inline two methods with the same name? -> add attribute at target method level?

        helper = BytecodePatchHelper(target)

        # Simple as that, we cannot do this!
        if helper.is_async and not self.is_async:
            raise RuntimeError(
                f"cannot inline a async method into an non-async context! ({target.target} into {self.patcher.target})"
            )

        if helper.is_async:
            # print("encountered ASYNC method")
            if helper.instruction_listing[0].opname == "GEN_START":
                helper.deleteRegion(0, 1)

        # Remove the initial RESUME opcode as it is not needed twice
        if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
            if helper.instruction_listing[0].opcode == Opcodes.RESUME:
                helper.deleteRegion(0, 1)
            if helper.instruction_listing[1].opcode == Opcodes.RESUME:
                helper.deleteRegion(1, 2)

            if helper.instruction_listing[0].opcode == Opcodes.COPY_FREE_VARS:
                instr = helper.instruction_listing[0]
                helper.deleteRegion(0, 1)

                if self.instruction_listing[0].opcode != Opcodes.COPY_FREE_VARS:
                    self.insertRegion(
                        0,
                        [instr],
                    )

        inner_name2outer_name: typing.Dict[str, typing.Tuple[int, str]] = {}

        # Walk across the code and look out of captures and outer returns
        # and make them our special instructions which are not changed afterwards
        index = -1
        while index != len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                if instr.opname == self.CALL_FUNCTION_NAME and instr.arg <= 1:
                    func_load_index, func_load = next(helper.findSourceOfStackIndexWithIndex(index, instr.arg, re_eval=False))

                    if func_load.opname in (
                        "LOAD_GLOBAL",
                        "LOAD_DEREF",
                    ) and func_load.argval in (
                        "capture_local",
                        "capture_local_static",
                    ):
                        local_instr_index, local_instr = next(helper.findSourceOfStackIndexWithIndex(index, 0, re_eval=False))

                        if local_instr.opcode != Opcodes.LOAD_CONST:
                            raise RuntimeError("can capture locals only from constant names")

                        outer_local = local_instr.argval

                        # todo: use findTargetOfStackIndex
                        possible_store = helper.instruction_listing[index + 1]

                        if (
                            possible_store.opcode == Opcodes.STORE_FAST
                            and func_load.argval == "capture_local"
                        ):
                            capture_store_target = possible_store.argval

                            inner_name2outer_name[capture_store_target] = self.patcher.ensureVarName(outer_local), outer_local

                            # CALL_FUNCTION 1                {index+0}
                            # STORE_FAST <new local name>    {index+1}
                            helper.deleteRegion(index, index + 2)

                            # LOAD_CONST <local name>        {index-1}
                            helper.deleteRegion(local_instr_index, local_instr_index + 1)

                            # LOAD_<method> "capture_local"  {index-2}
                            helper.deleteRegion(func_load_index, func_load_index + 1, maps_invalid_to=func_load_index)

                            # print(f"found local variable access onto '{local}' from '{capture_target}' "
                            #       f"(var index: {self.patcher.ensureVarName(local)}) at {index} ({instr})")
                            index -= 1

                        # We don't really know what is done to the local,
                        # so we need to store it as it is on the stack
                        # This branch is also the only branch for capture_local_static() as than
                        # it is stored wherever it is needed
                        else:
                            # LOAD_FAST replacing function call opcode
                            helper.instruction_listing[index - 2] = createInstruction(Opcodes.LOAD_FAST_OUTER, self.patcher.ensureVarName(outer_local), outer_local)

                            # CALL_FUNCTION 1                {index+0}
                            helper.deleteRegion(index, index + 1)

                            # LOAD_CONST <local name>        {index-1}
                            helper.deleteRegion(local_instr_index, local_instr_index + 1)

                        break

                    if func_load.opname in (
                        "LOAD_GLOBAL",
                        "LOAD_DEREF",
                    ) and func_load.argval == "injected_return":
                        helper.instruction_listing[index] = createInstruction(Opcodes.RETURN_OUTER)

                        if instr.arg == 0:
                            helper.insertRegion(index, helper.patcher.createLoadConst(None))

                        helper.deleteRegion(func_load_index, func_load_index + 1, maps_invalid_to=func_load_index)
                        index -= 1
                        break

            else:
                break

        # Rebind locals; The ones we expose outers with will become temporary opcodes; and the other ones get the special name
        for index, instr in helper.walk():
            if instr.opcode == Opcodes.LOAD_FAST and instr.argval in inner_name2outer_name:
                helper.instruction_listing[index] = createInstruction(Opcodes.LOAD_FAST_OUTER, *inner_name2outer_name[instr.argval])
            elif instr.opcode == Opcodes.STORE_FAST and instr.argval in inner_name2outer_name:
                helper.instruction_listing[index] = createInstruction(Opcodes.STORE_FAST_OUTER, *inner_name2outer_name[instr.argval])
            elif instr.opcode == Opcodes.DELETE_FAST and instr.argval in inner_name2outer_name:
                helper.instruction_listing[index] = createInstruction(Opcodes.DELETE_FAST_OUTER, *inner_name2outer_name[instr.argval])
            elif instr.opcode in dis.haslocal:
                name = helper.patcher.target.__name__ + "::" + instr.argval
                helper.instruction_listing[index] = reconstruct_instruction(instr, self.patcher.ensureVarName(name), name)

        # Return becomes jump instruction, the function TAIL is currently not known,
        # so we need to trick it a little by setting its value to 0, and later waling over it and rebinding that
        # instructions to the correct offset

        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1

            for index, instr in list(helper.walk())[index:]:
                if instr.opname == "RETURN_VALUE":
                    helper.instruction_listing[index] = createInstruction(Opcodes.JUMP_TO_INJECTION_END)

                    # If we want to discard the returned result, we need to add a POP_TOP instruction
                    if discard_return_result:
                        helper.insertRegion(index, [createInstruction("POP_TOP")])

                    break
            else:
                break

        # The last return statement does not need a jump_absolute wrapper, as it continues into
        # normal code
        size = len(helper.instruction_listing)
        if helper.instruction_listing[size - 1].opcode != Opcodes.JUMP_TO_INJECTION_END:
            raise RuntimeError(f"something went horribly wrong, got {helper.instruction_listing[size - 1]} instead of a JUMP_TO_INJECTION_END instruction!")

        helper.deleteRegion(size - 1, size)

        instructions = list(helper.walk())

        # Now rebind all instructions requiring data outside the code array
        for index, instr in instructions:
            if instr.opcode in dis.hasconst:
                # print("constant", instr)
                helper.instruction_listing[index] = reconstruct_instruction(
                    instr,
                    self.patcher.ensureConstant(instr.argval),
                )

            elif instr.opcode in dis.haslocal:
                name = instr.argval
                # print(f"rebinding real local '{instr.argval}' to '{name}'", instr, index)
                helper.instruction_listing[index] = reconstruct_instruction(
                    instr,
                    self.patcher.ensureVarName(name),
                    name,
                )

            elif instr.opcode in dis.hasname:
                i = self.patcher.ensureName(instr.argval)
                helper.instruction_listing[index] = createInstruction(
                    instr.opname,
                    i,
                )

        # And now insert the code into our code
        # todo: check for HEAD generator instruction -> remove if there

        bind_locals = [
            self.patcher.createStoreFast(e)
            for e in reversed([target.target.__name__ + "::" + e for e in target.variable_names[:added_args]])
        ] + list(
            helper.patcher.create_default_write_opcodes(
                added_args, ensure_target=self.patcher, prefix=target.target.__name__ + "::"
            )
        )

        # Rewire JUMP_ABSOLUTE instructions to the new offset
        for index, instr in helper.walk():
            if instr.opcode in JUMP_ABSOLUTE and instr.arg != 0:
                helper.instruction_listing[index] = reconstruct_instruction(
                    instr, instr.arg + start
                )

        # print(self.patcher.target, helper.patcher.target, bind_locals)

        self.insertRegion(
            start,
            bind_locals
            + list(inter_code)
            + helper.instruction_listing
            + [
                createInstruction(Opcodes.INJECTION_TAIL_TRACK)
            ],
        )

        self.patcher.max_stack_size += target.max_stack_size
        self.patcher.number_of_locals += target.number_of_locals

        # Find out where the old instruction ended
        for index, instr in self.walk():
            if instr.opcode == Opcodes.INJECTION_TAIL_TRACK:
                self.deleteRegion(index, index+1)
                tail_index = index
                break
        else:
            self.print_stats()
            raise RuntimeError("Tail not found after insertion!")

        for index, instr in list(self.walk())[start:tail_index]:

            # Bind the JUMP_ABSOLUTE calls for jumping out of the injected now to the correct tail
            if instr.opcode == Opcodes.JUMP_TO_INJECTION_END:
                self.instruction_listing[index] = createInstruction(
                    UNCONDITIONAL_JUMPS[1], len(helper.instruction_listing) - index
                )

            # Remap the captures local instructions
            elif instr.opcode == Opcodes.LOAD_FAST_OUTER:
                self.instruction_listing[index] = createInstruction(Opcodes.LOAD_FAST, instr.arg, instr.argval)
            elif instr.opcode == Opcodes.STORE_FAST_OUTER:
                self.instruction_listing[index] = createInstruction(Opcodes.STORE_FAST, instr.arg, instr.argval)
            elif instr.opcode == Opcodes.DELETE_FAST_OUTER:
                self.instruction_listing[index] = createInstruction(Opcodes.DELETE_FAST, instr.arg, instr.argval)
            elif instr.opcode == Opcodes.RETURN_OUTER:
                self.instruction_listing[index] = createInstruction(Opcodes.RETURN_VALUE)

        try:
            self.store()
        except:
            self.print_stats()
            raise

        return tail_index

    def insertMethodMultipleTimesAt(
        self,
        start: typing.List[int],
        method: MutableCodeObject,
        force_multiple_inlines=False,
        added_args=0,
        discard_return_result=True,
        inter_code=tuple(),
    ):
        """
        Similar to insertMethodAt(), but is able to do some more optimisations in how to inject the method.
        Works best when used with multiple injection targets

        :param start: the start to inject at
        :param method: the method to inject
        :param force_multiple_inlines: if we should force multiple inlines for each method call, or if we can
            optimise stuff
        :param added_args: how many positional args are added to the method call
        :param discard_return_result: if the return result should be deleted or not
        :param inter_code: what code to insert between arg getting and function invoke
        """
        offset = 0
        for index in sorted(start):
            offset += (
                self.insertMethodAt(
                    index + offset,
                    method,
                    added_args=added_args,
                    discard_return_result=discard_return_result,
                    inter_code=inter_code,
                )
                - index
            )
        return self

    def makeMethodAsync(self):
        """
        Simply makes this method async, like it was declared by "async def"
        """
        # don't insert the GEN_START instruction twice
        # todo: set correct flag on the __code__
        if self.is_async:
            return

        self.insertRegion(0, [createInstruction("GEN_START", 2)])
        self.is_async = True
        self.patcher.flags |= inspect.CO_COROUTINE
        return self

    def makeMethodSync(self):
        """
        Simply makes this method sync, like it was declared without "async def"
        WARNING: this transform is normally no good idea!
        """
        if not self.is_async:
            return

        # todo: set correct flag on the __code__

        assert self.instruction_listing[0].opname == "GEN_START"

        self.deleteRegion(0, 1)
        self.is_async = False
        self.patcher.flags ^= inspect.CO_COROUTINE
        return self

    CALL_FUNCTION_NAME = None

    if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
        CALL_FUNCTION_NAME = "CALL_NO_KW"
    else:
        CALL_FUNCTION_NAME = "CALL_FUNCTION"

    def insertGivenMethodCallAt(
        self,
        offset: int,
        method: typing.Callable,
        *args,
        collected_locals=tuple(),
        pop_result=True,
        include_stack_top_copy=False,
        special_args_collectors: typing.Iterable[dis.Instruction] = tuple(),
        insert_after=tuple(),
    ):
        """
        Injects the given method as a constant call into the bytecode of that function
        Use insertMethodAt() instead when wanting to inline that call

        :param offset: the offset to inject at
        :param method: the method to inject
        :param collected_locals: what locals to send to the method call
        :param pop_result: if to pop the result
        :param include_stack_top_copy: if to add the stack top as the last parameter
        :param special_args_collectors: args collecting instructions for some stuff,
            the entry count represents the arg count added here
        :param insert_after: an iterable of instructions to insert after the method call
        """
        self.insertRegion(
            offset,
            ([createInstruction("DUP_TOP")] if include_stack_top_copy else [])
            + [self.patcher.createLoadConst(method)]
            + ([createInstruction("ROT_TWO")] if include_stack_top_copy else [])
            + [self.patcher.createLoadConst(e) for e in reversed(args)]
            + [self.patcher.createLoadFast(e) for e in reversed(collected_locals)]
            + list(special_args_collectors)
            + [
                createInstruction(
                    self.CALL_FUNCTION_NAME,
                    len(args)
                    + len(collected_locals)
                    + int(include_stack_top_copy)
                    + len(special_args_collectors),
                )
            ]
            + ([createInstruction("POP_TOP")] if pop_result else [])
            + list(insert_after),
        )
        self.patcher.max_stack_size += (
            1
            + len(args)
            + len(collected_locals)
            + int(include_stack_top_copy)
            + len(special_args_collectors)
        )
        return self

    def insertStaticMethodCallAt(
        self, offset: int, method: typing.Union[str, typing.Callable], *args
    ):
        """
        Injects a static method call into another method
        :param offset: the offset to inject at, from function head
        :param method: the method address to inject, by module:path, or the method itself
        :param args: the args to invoke with

        WARNING: due to the need of a dynamic import instruction, the method to inject into cannot lie in the same
            package as the method call to inject
        """

        if isinstance(method, str):
            module, path = method.split(":")
            real_name = path.split(".")[-1]

            if path.count(".") > 0:
                real_module = module + "." + ".".join(path.split(".")[:-1])
            else:
                real_module = module

            instructions = [
                self.patcher.createLoadConst(0),
                self.patcher.createLoadConst((real_name,)),
                createInstruction("IMPORT_NAME", self.patcher.ensureName(real_module)),
                createInstruction("IMPORT_FROM", self.patcher.ensureName(real_name)),
                self.patcher.createStoreFast(real_module),
                createInstruction("POP_TOP"),
                self.patcher.createLoadFast(real_module),
            ]
        else:
            instructions = [self.patcher.createLoadConst(method)]

        instructions += [self.patcher.createLoadConst(e) for e in args]

        instructions += [
            createInstruction(self.CALL_FUNCTION_NAME, len(args)),
            createInstruction("POP_TOP"),
        ]

        self.patcher.max_stack_size += max(2, len(args))
        self.patcher.number_of_locals += 1
        self.patcher.variable_names.append(real_name)

        self.insertRegion(
            offset,
            instructions,
        )
        return self

    def insertAsyncStaticMethodCallAt(
        self, offset: int, method: typing.Union[str, typing.Callable], *args
    ):
        """
        Injects a static method call to an async method into another method
        :param offset: the offset to inject at, from function head
        :param method: the method address to inject, by module:path, or the method instance itself
        :param args: the args to invoke with

        WARNING: due to the need of a dynamic import instruction, the method to inject into cannot lie in the same
            package as the method call to inject
        """

        if not self.is_async:
            raise RuntimeError(
                "cannot insert async method call when surrounding method is not async"
            )

        if isinstance(method, str):
            module, path = method.split(":")
            real_name = path.split(".")[-1]

            if path.count(".") > 0:
                real_module = module + "." + ".".join(path.split(".")[:-1])
            else:
                real_module = module

            instructions = [
                self.patcher.createLoadConst(0),
                self.patcher.createLoadConst((real_name,)),
                createInstruction("IMPORT_NAME", self.patcher.ensureName(real_module)),
                createInstruction("IMPORT_FROM", self.patcher.ensureName(real_name)),
                self.patcher.createStoreFast(real_module),
                createInstruction("POP_TOP"),
                self.patcher.createLoadFast(real_module),
            ]
        else:
            instructions = [
                self.patcher.createLoadConst(method),
            ]

        instructions += [self.patcher.createLoadConst(e) for e in args]
        instructions += [createInstruction(self.CALL_FUNCTION_NAME, len(args))]

        # Ok, at this point on the stack top is the awaitable object
        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            instructions += [
                createInstruction("GET_AWAITABLE"),
                self.patcher.createLoadConst(None),
                createInstruction("YIELD_FROM"),
                createInstruction("POP_TOP"),
            ]
        else:
            instructions += [
                createInstruction("GET_AWAITABLE"),
                self.patcher.createLoadConst(None),
                createInstruction("SEND", 2),
                createInstruction("RESUME", 3),
                createInstruction(
                    "JUMP_ABSOLUTE", offset + len(instructions) + 3
                ),  # JUMP to SEND
                createInstruction("POP_TOP"),
            ]

        self.patcher.max_stack_size += max(2, len(args))

        self.insertRegion(
            offset,
            instructions,
        )
        return self

    def insertObjectBoundMethodCall(
        self,
        index: int,
        name: str,
        object_local_index: typing.Union[str, int] = "self",
        take_from_stack_top=False,
        args=tuple(),
        add_args_from_locals: typing.Tuple[str] = tuple(),
        method_instance=None,
    ):
        """
        Inserts an object bound method call

        :param index: where to insert the method call
        :param name: the method name; can be None when method_accessor is not None
        :param object_local_index: where the object is from
        :param take_from_stack_top: if the object is the stack top
        :param args: the args to give the function
        :param add_args_from_locals: what locals to add as args
        :param method_instance: optional, the method instance; takes priority over the method name

        todo: add possibility for kwargs
        todo: add async variant
        """
        if name is None and method_instance is None:
            raise ValueError(
                "either the method name or the method instance must be set"
            )

        if isinstance(object_local_index, str) and method_instance is None:
            object_local_index = self.patcher.ensureVarName(object_local_index)

        arg_count = len(args) + len(add_args_from_locals)

        if method_instance is None:
            instructions = [
                createInstruction("LOAD_FAST", object_local_index),
                createInstruction("LOAD_METHOD", self.patcher.ensureName(name)),
            ]
        else:
            instructions = [
                self.patcher.createLoadConst(method_instance),
                self.patcher.createLoadFast(object_local_index)
                if not take_from_stack_top
                else createInstruction("DUP_TOP"),
            ]
            arg_count += 1

        instructions += [
            self.patcher.createLoadFast(e) for e in reversed(add_args_from_locals)
        ]

        instructions += [self.patcher.createLoadConst(e) for e in reversed(args)]

        if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
            if method_instance is None:
                instructions += [
                    createInstruction("PRECALL_METHOD", arg_count),
                ]

            instructions += [
                createInstruction("CALL_NO_KW", arg_count),
                createInstruction("POP_TOP"),
            ]
        else:
            if method_instance is None:
                instructions += [
                    createInstruction("CALL_METHOD", arg_count),
                    createInstruction("POP_TOP"),
                ]

            else:
                instructions += [
                    createInstruction("CALL_FUNCTION", arg_count),
                    createInstruction("POP_TOP"),
                ]

        self.insertRegion(index, instructions)

    def print_stats(self):
        try:
            self.store()
        except:
            traceback.print_exc()
            for i, instr in enumerate(self.instruction_listing):
                print(i * 2, instr)
            return

        print(f"{self.__class__.__name__} stats around {self.patcher.target}")

        for i, instr in self.walk():
            print(i * 2, instr)

        print("Raw code:", self.patcher.code_string)
        print("Names:", self.patcher.names)
        print("Constants:", self.patcher.constants)
        print("Free vars:", self.patcher.free_vars)
        print("Cell vars:", self.patcher.cell_vars)

    def findSourceOfStackIndex(
        self, index: int, offset: int, re_eval=True
    ) -> typing.Iterator[dis.Instruction]:
        return (e[1] for e in self.findSourceOfStackIndexWithIndex(index, offset, re_eval=re_eval))

    def findSourceOfStackIndexWithIndex(
        self, index: int, offset: int, re_eval=True
    ) -> typing.Iterator[typing.Tuple[int, dis.Instruction]]:
        """
        Finds the source instruction of the given stack element.
        Uses advanced back-tracking in code
        todo: check the IS_JUMP_TARGET flag on our way and collect them
        todo: when encountering an non-conditional JUMP instruction, we are at our end of our journey

        :param index: current instruction index, before which we want to know the layout
        :param offset: the offset, where 0 is top, and all following numbers (1, 2, 3, ...) give the i+1-th
            element of the stack
        """
        from .CodeOptimiser import BUILD_PRIMITIVE

        if re_eval: self.re_eval_instructions()
        instructions = list(self.walk())
        # print(instructions)
        # print(index, offset)

        for index, instr in reversed(instructions[:index]):
            if offset < 0:
                raise RuntimeError(offset, instructions[index + 1])

            # print(instr, offset)

            if offset == 0:  # Currently, at top
                if instr.opcode in LOAD_SINGLE_VALUE:
                    yield index, instr
                    return

                elif (
                    instr.opcode in POP_DOUBLE_AND_PUSH_SINGLE
                    or instr.opcode in POP_SINGLE_AND_PUSH_SINGLE
                ):
                    yield index, instr
                    return

            if instr.opcode in POP_SINGLE_AND_PUSH_SINGLE or instr.opcode in DO_NOTHING:
                continue

            if instr.opcode in LOAD_SINGLE_VALUE:
                offset -= 1

            elif instr.opcode in POP_SINGLE_VALUE:
                offset += 1

            elif instr.opcode in POP_DOUBLE_AND_PUSH_SINGLE:
                offset += 1

            elif instr.opcode in POP_DOUBLE_VALUE:
                offset += 2

            elif instr.opcode in METHOD_CALL:
                offset += 1
                offset -= instr.arg - 1

            elif instr.opcode == Opcodes.UNPACK_SEQUENCE:
                offset += instr.arg - 1

            elif instr.opcode == Opcodes.FOR_ITER:
                raise ValueError

            elif instr.opcode == Opcodes.ROT_TWO:
                if offset == 0:
                    offset = 1
                elif offset == 1:
                    offset = 0

            elif instr.opcode == Opcodes.ROT_THREE:
                if offset == 0:
                    offset = 2
                elif offset == 1:
                    offset = 0
                elif offset == 2:
                    offset = 1

            elif instr.opcode == Opcodes.ROT_FOUR:
                if offset == 0:
                    offset = 3
                elif offset == 1:
                    offset = 0
                elif offset == 2:
                    offset = 1
                elif offset == 3:
                    offset = 2

            elif instr.opcode == Opcodes.DUP_TOP:
                if offset > 0:
                    offset -= 1

            elif instr.opcode == Opcodes.DUP_TOP_TWO:
                if offset > 1:
                    offset -= 2

            elif instr.opcode in BUILD_PRIMITIVE:
                offset += 1
                offset -= instr.arg - 1

            elif instr.opcode == Opcodes.BUILD_MAP:
                offset += 1
                offset -= instr.arg * 2 - 1

            elif (
                sys.version_info.major >= 3
                and sys.version_info.minor >= 11
                and instr.opcode == Opcodes.BINARY_OP
            ):
                pass

            else:
                raise NotImplementedError(instr)

        if offset < 0:
            raise RuntimeError

    def findTargetOfStackIndex(self, index: int, offset: int):
        """
        Yields the source instructions for the data found at "index", where 0 is top, 1 is second from top, ...
        """
        self.re_eval_instructions()
        instructions = list(self.walk())
        # print(instructions)
        # print(index, offset)

        # todo: follow unconditional jumps
        # todo: possible branch at conditional jumps

        for index, instr in instructions[index+1:]:
            if offset >= len(instructions):
                raise RuntimeError(offset, instructions[index + 1])

            # print(instr, offset)

            if offset == 0:  # Currently, at top
                if instr.opcode in POP_SINGLE_VALUE or instr.opcode in POP_DOUBLE_VALUE:
                    yield instr
                    return

            if offset <= 1:
                if (
                    instr.opcode in POP_DOUBLE_AND_PUSH_SINGLE
                    or instr.opcode in POP_SINGLE_AND_PUSH_SINGLE
                ):
                    yield instr
                    return

            if instr.opcode == Opcodes.CALL_METHOD and offset <= instr.arg:
                yield instr
                return

            if instr.opcode == Opcodes.CALL_FUNCTION_KW and offset <= instr.arg + 1:
                yield instr
                return

            if instr.opcode == Opcodes.BUILD_TUPLE:
                if offset < instr.arg:
                    yield instr
                    return
                offset -= instr.arg - 1
                continue

            if instr.opcode in POP_SINGLE_AND_PUSH_SINGLE or instr.opcode in DO_NOTHING:
                continue

            if instr.opcode in LOAD_SINGLE_VALUE:
                offset += 1

            elif instr.opcode in POP_SINGLE_VALUE:
                offset -= 1

            elif instr.opcode in POP_DOUBLE_AND_PUSH_SINGLE:
                offset -= 1

            elif instr.opcode in POP_DOUBLE_VALUE:
                offset -= 2

            elif instr.opcode in METHOD_CALL:
                offset -= 1
                offset += instr.arg - 1

            elif instr.opcode == Opcodes.CALL_FUNCTION_KW:
                offset -= 1
                offset += instr.arg

            elif instr.opcode == Opcodes.UNPACK_SEQUENCE:
                offset -= instr.arg - 1

            elif instr.opcode == Opcodes.FOR_ITER:
                raise ValueError

            elif instr.opcode == Opcodes.ROT_TWO:
                if offset == 0:
                    offset = 1
                elif offset == 1:
                    offset = 0

            elif instr.opcode == Opcodes.ROT_THREE:
                if offset == 0:
                    offset = 2
                elif offset == 1:
                    offset = 0
                elif offset == 2:
                    offset = 1

            elif instr.opcode == Opcodes.ROT_FOUR:
                if offset == 0:
                    offset = 3
                elif offset == 1:
                    offset = 0
                elif offset == 2:
                    offset = 1
                elif offset == 3:
                    offset = 2

            elif instr.opcode == Opcodes.DUP_TOP:
                if offset > 0:
                    offset += 1

            elif instr.opcode == Opcodes.DUP_TOP_TWO:
                if offset > 1:
                    offset += 2

            elif (
                sys.version_info.major >= 3
                and sys.version_info.minor >= 11
                and instr.opcode == Opcodes.BINARY_OP
            ):
                pass

            else:
                raise NotImplementedError(instr)

        if offset < 0:
            raise RuntimeError

    def evalStaticFrom(self, instruction: dis.Instruction):
        if instruction.opcode == Opcodes.LOAD_CONST:
            return instruction.argval

        if instruction.opcode == Opcodes.LOAD_GLOBAL:
            try:
                return self.patcher.target.__globals__[instruction.argval]
            except KeyError:
                try:
                    return globals()[instruction.argval]
                except KeyError:
                    return eval(instruction.argval)

        raise ValueError
