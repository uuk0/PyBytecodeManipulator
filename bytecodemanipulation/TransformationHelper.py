import dis
import inspect
import sys
import traceback
import types
import typing

from bytecodemanipulation.MutableCodeObject import MutableCodeObject, createInstruction

from .util import Opcodes


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


OFFSET_JUMPS = dis.hasjrel
REAL_JUMPS = dis.hasjabs

DO_NOTHING = {
    Opcodes.NOP,
}
LOAD_SINGLE_VALUE = {
    Opcodes.LOAD_FAST,
    Opcodes.LOAD_CONST,
    Opcodes.LOAD_DEREF,
    Opcodes.LOAD_GLOBAL,
    Opcodes.LOAD_BUILD_CLASS,
    Opcodes.LOAD_NAME,
    Opcodes.LOAD_CLASSDEREF,
}
POP_SINGLE_VALUE = {
    Opcodes.POP_TOP,
    Opcodes.STORE_FAST,
    Opcodes.STORE_DEREF,
    Opcodes.STORE_GLOBAL,
    Opcodes.STORE_NAME,
    Opcodes.PRINT_EXPR,
    Opcodes.YIELD_VALUE,
}
POP_DOUBLE_VALUE = {
    Opcodes.STORE_ATTR,
    Opcodes.STORE_SUBSCR,
}
POP_DOUBLE_AND_PUSH_SINGLE = {
    Opcodes.STORE_SUBSCR,
    Opcodes.DELETE_SUBSCR,
    Opcodes.STORE_ATTR,
    Opcodes.BINARY_POWER,
    Opcodes.BINARY_MULTIPLY,
    Opcodes.BINARY_MATRIX_MULTIPLY,
    Opcodes.BINARY_FLOOR_DIVIDE,
    Opcodes.BINARY_TRUE_DIVIDE,
    Opcodes.BINARY_MODULO,
    Opcodes.BINARY_ADD,
    Opcodes.BINARY_SUBTRACT,
    Opcodes.BINARY_SUBSCR,
    Opcodes.BINARY_LSHIFT,
    Opcodes.BINARY_RSHIFT,
    Opcodes.BINARY_AND,
    Opcodes.BINARY_XOR,
    Opcodes.BINARY_OR,
    Opcodes.INPLACE_POWER,
    Opcodes.INPLACE_MULTIPLY,
    Opcodes.INPLACE_MATRIX_MULTIPLY,
    Opcodes.INPLACE_FLOOR_DIVIDE,
    Opcodes.INPLACE_TRUE_DIVIDE,
    Opcodes.INPLACE_MODULO,
    Opcodes.INPLACE_ADD,
    Opcodes.INPLACE_SUBTRACT,
    Opcodes.INPLACE_LSHIFT,
    Opcodes.INPLACE_RSHIFT,
    Opcodes.INPLACE_AND,
    Opcodes.INPLACE_XOR,
    Opcodes.INPLACE_OR,
}
POP_SINGLE_AND_PUSH_SINGLE = {
    Opcodes.LOAD_METHOD,
    Opcodes.UNARY_POSITIVE,
    Opcodes.UNARY_NEGATIVE,
    Opcodes.UNARY_NOT,
    Opcodes.UNARY_INVERT,
    Opcodes.GET_ITER,
    Opcodes.GET_YIELD_FROM_ITER,
    Opcodes.GET_AWAITABLE,
    Opcodes.GET_AITER,
    Opcodes.GET_ANEXT,
}


if sys.version_info.major <= 3 and sys.version_info.minor < 11:
    POP_SINGLE_VALUE |= {
        Opcodes.YIELD_FROM,
    }
    METHOD_CALL = Opcodes.CALL_METHOD
else:
    DO_NOTHING |= {
        Opcodes.RESUME,
        Opcodes.COPY_FREE_VARS,
    }
    METHOD_CALL = Opcodes.CALL_NO_KW


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
            else MutableCodeObject(patcher)
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

        if self.is_verbose and not force: return
        self.is_verbose = True

        self.store()
        internal = self.patcher.create_method_from()

        # test and test2 are only placeholder constants later replaced by the real values via
        # bytecode manipulation; this removes the need of cellvars/freevars

        def invoke(*args, **kwargs):
            from bytecodemanipulation.Emulator import CURRENT
            return CURRENT.execute("test", *args, invoke_subcalls_via_emulator="test2", **kwargs)

        patcher = MutableCodeObject(invoke)

        # bind the code object as a constant
        patcher.constants[patcher.constants.index("test")] = internal
        patcher.constants[patcher.constants.index("test2")] = verbose_internal_calls

        patcher.free_vars = self.patcher.free_vars
        patcher.cell_vars = self.patcher.cell_vars
        self.patcher.overrideFrom(patcher)
        self.patcher.applyPatches()

        self.patcher = MutableCodeObject(internal)
        self.instruction_listing = list(self.patcher.get_instruction_list())
        return self

    def walk(self) -> typing.Iterable[typing.Tuple[int, dis.Instruction]]:
        yield from zip(range(len(self.instruction_listing)), self.instruction_listing)

    def store(self):
        self.patcher.instructionList2Code(self.instruction_listing)

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

        def rebind_offset(o: int) -> int:
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
            if instr.opcode in OFFSET_JUMPS:
                offset = instr.arg
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_offset(offset)
                )

            elif instr.opcode in REAL_JUMPS:
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_real(instr.arg)
                )

        del self.instruction_listing[start:end]

    def insertRegion(self, start: int, instructions: typing.List[dis.Instruction]):
        """
        Inserts a list of instructions into the opcode list, resolving the jumps in code correctly

        WARNING: the user is required to make sure that stack & variable constraints still hold

        :param start: where to start the insertion, the first instruction becomes the start index
        :param instructions: list of instructions to insert
        """
        size = len(instructions)

        def rebind_offset(o: int) -> int:
            nonlocal i

            # If we jump OVER the region
            if i + o >= start > i:
                return o + size

            if i + o < start <= i:
                return o - size

            return o

        def rebind_real(o: int) -> int:

            # If we jump OVER the region
            if o >= start:
                return o - size

            return o

        for i, instr in self.walk():
            # Check control flow
            if instr.opcode in OFFSET_JUMPS:
                offset = instr.arg
                self.instruction_listing[i] = reconstruct_instruction(
                    instr, arg=rebind_offset(offset)
                )

            elif instr.opcode in REAL_JUMPS:
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
            method = MutableCodeObject(method)

        target = method.copy()

        # Rebind all inner local variables to something we cannot possibly enter as code,
        # so we cannot get conflicts (in the normal case)
        # todo: what happens if we inline a method with the same name?
        target.variable_names = [
            method.target.__name__ + "::" + e for e in target.variable_names
        ]

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

        # Rewire JUMP_ABSOLUTE instructions to the new offset
        for index, instr in helper.walk():
            if instr.opname == "JUMP_ABSOLUTE":
                helper.instruction_listing[index] = reconstruct_instruction(
                    instr, instr.arg + start
                )

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


        captured = {}
        captured_indices = set()
        captured_names = set()

        protect = set()

        # Walk across the code and look out of captures

        index = -1
        while index != len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                # print(index, instr, self.CALL_FUNCTION_NAME)

                if instr.opname == self.CALL_FUNCTION_NAME and index > 1:
                    possible_load = helper.instruction_listing[index - 2]

                    # print(index, instr, self.CALL_FUNCTION_NAME, possible_load)

                    if possible_load.opname in (
                        "LOAD_GLOBAL",
                        "LOAD_DEREF",
                    ) and possible_load.argval in (
                        "capture_local",
                        "capture_local_static",
                    ):
                        assert (
                            helper.instruction_listing[index - 1].opname == "LOAD_CONST"
                        ), "captured must be local var"

                        local = helper.instruction_listing[index - 1].argval

                        # print(f"captured local '{local}'")

                        if (
                            helper.instruction_listing[index + 1].opname == "STORE_FAST"
                            and possible_load.argval == "capture_local"
                        ):
                            capture_target = helper.instruction_listing[
                                index + 1
                            ].argval

                            captured[
                                capture_target
                            ] = local, self.patcher.ensureVarName(local)
                            captured_indices.add(index)
                            captured_names.add(local)

                            # LOAD_<method> "capture_local"  {index-2}
                            # LOAD_CONST <local name>        {index-1}
                            # CALL_FUNCTION 1                {index+0}
                            # STORE_FAST <new local name>    {index+1}
                            helper.deleteRegion(index - 2, index + 2)

                            # print(f"found local variable access onto '{local}' from '{capture_target}' "
                            #       f"(var index: {self.patcher.ensureVarName(local)}) at {index} ({instr})")
                            index -= 1

                        # We don't really know what is done to the local,
                        # so we need to store it as it is on the stack
                        # This branch is also the only branch for capture_local_static() as than
                        # it is stored wherever it is needed
                        else:
                            captured_names.add(local)

                            # LOAD_<method> "capture_local"  {index-2}
                            # LOAD_CONST <local name>        {index-1}
                            # CALL_FUNCTION 1                {index+0}
                            helper.deleteRegion(index - 2, index + 1)
                            helper.insertRegion(
                                index - 2,
                                [self.patcher.createLoadFast(local)],
                            )

                            # print(f"found local variable read-only access onto '{local}';"
                            #       f" replacing with link to real local at index {self.patcher.ensureVarName(local)}")

                        break
            else:
                break

        # print("protected", ("'" + "', '".join(captured_names) + "'") if captured_names else "null")

        # Rebind the captured locals
        for index, instr in list(helper.walk()):
            if instr.opcode in dis.haslocal:
                if instr.argval in captured and index not in captured_indices:
                    name, i = captured[instr.argval]
                    helper.instruction_listing[index] = dis.Instruction(
                        instr.opname,
                        instr.opcode,
                        i,
                        name,
                        name,
                        0,
                        0,
                        False,
                    )
                    protect.add(index)
                    # print(f"transforming local access at {index}: '{instr.argval}' to "
                    #       f"'{name}' (old index: {instr.arg}, new: {i}) ({instr})")

        # Return becomes jump instruction, the function TAIL is currently not known,
        # so we need to trick it a little by setting its value to 0, and later waling over it and rebinding that
        # instructions to the correct offset

        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1

            for index, instr in list(helper.walk())[index:]:
                if instr.opname == "RETURN_VALUE":
                    helper.deleteRegion(index, index + 1)

                    # If we want to discard the returned result, we need to add a POP_TOP instruction
                    if discard_return_result:
                        helper.insertRegion(
                            index,
                            [
                                createInstruction("POP_TOP"),
                                createInstruction("JUMP_ABSOLUTE", 0, 0),
                            ],
                        )
                    else:
                        helper.insertRegion(
                            index,
                            [createInstruction("JUMP_ABSOLUTE", 0, 0)],
                        )
                    break
            else:
                break

        # The last return statement does not need a jump_absolute wrapper, as it continues into
        # normal code
        size = len(helper.instruction_listing)
        assert (
            helper.instruction_listing[size - 1].opname == "JUMP_ABSOLUTE"
        ), f"something went horribly wrong, got {helper.instruction_listing[size - 1]}!"
        helper.deleteRegion(size - 1, size)

        index = -1
        while index < len(helper.instruction_listing) - 1:
            index += 1
            for index, instr in list(helper.walk())[index:]:
                if instr.opname == self.CALL_FUNCTION_NAME and index > 1:
                    if instr.arg == 1:
                        possible_load = helper.instruction_listing[index - 2]

                        if (
                            possible_load.opname in ("LOAD_GLOBAL", "LOAD_DEREF")
                            and possible_load.argval == "injected_return"
                        ):
                            # Delete the LOAD_GLOBAL instruction
                            helper.instruction_listing[index] = createInstruction(
                                "RETURN_VALUE"
                            )
                            helper.deleteRegion(
                                index + 1, index + 2, maps_invalid_to=index + 1
                            )
                            helper.deleteRegion(index - 2, index - 1)
                            index -= 3
                            protect.add(index)
                            break

                    elif instr.arg == 0:
                        possible_load = helper.instruction_listing[index - 1]

                        if (
                            possible_load.opname == "LOAD_GLOBAL"
                            and possible_load.argval == "injected_return"
                        ):
                            helper.instruction_listing[
                                index - 1
                            ] = self.patcher.createLoadConst(None)
                            helper.instruction_listing[index] = createInstruction(
                                "RETURN_VALUE"
                            )
                            helper.deleteRegion(
                                index + 1, index + 2, maps_invalid_to=index + 1
                            )
                            helper.deleteRegion(index - 2, index - 1)
                            index -= 3
                            protect.add(index - 1)
                            break
            else:
                break

        instructions = list(helper.walk())
        # print(instructions)

        # Now rebind all
        for index, instr in instructions:
            if index in protect:
                continue

            if instr.opcode in dis.hasconst:
                # print("constant", instr)
                helper.instruction_listing[index] = reconstruct_instruction(
                    instr,
                    self.patcher.ensureConstant(instr.argval),
                )

            elif instr.opcode in dis.haslocal and instr.argval not in captured_names:
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
            for e in reversed(target.variable_names[:added_args])
        ] + list(
            helper.patcher.create_default_write_opcodes(
                added_args, ensure_target=self.patcher
            )
        )

        # print(self.patcher.target, helper.patcher.target, bind_locals)

        self.insertRegion(
            start,
            bind_locals
            + list(inter_code)
            + helper.instruction_listing
            + [
                self.patcher.createLoadConst("injected:internal"),
                createInstruction("POP_TOP"),
            ],
        )

        self.patcher.max_stack_size += target.max_stack_size
        self.patcher.number_of_locals += target.number_of_locals

        try:
            self.store()
        except:
            self.print_stats()
            raise

        # self.print_stats()

        # Find out where the old instruction ended
        for index, instr in self.walk():
            if instr.opname == "LOAD_CONST" and instr.argval == "injected:internal":
                following = self.instruction_listing[index + 1]
                assert following.opname == "POP_TOP"
                self.deleteRegion(index, index + 2)
                tail_index = index
                break
        else:
            self.print_stats()
            raise RuntimeError("Tail not found after insertion!")

        for index, instr in list(self.walk())[start:tail_index]:
            if instr.opname == "JUMP_ABSOLUTE" and instr.argval == 0:
                self.instruction_listing[index] = reconstruct_instruction(
                    instr,
                    tail_index,
                )

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
            offset += self.insertMethodAt(index+offset, method, added_args=added_args, discard_return_result=discard_return_result, inter_code=inter_code) - index
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

    def insertStaticMethodCallAt(self, offset: int, method: typing.Union[str, typing.Callable], *args):
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
            instructions = [
                self.patcher.createLoadConst(method)
            ]

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

    def insertAsyncStaticMethodCallAt(self, offset: int, method: typing.Union[str, typing.Callable], *args):
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
                createInstruction("JUMP_ABSOLUTE", offset + len(instructions) + 3),  # JUMP to SEND
                createInstruction("POP_TOP"),
            ]

        self.patcher.max_stack_size += max(2, len(args))

        self.insertRegion(
            offset,
            instructions,
        )
        return self

    @staticmethod
    def prepare_method_for_insert(method: MutableCodeObject) -> MutableCodeObject:
        """
        Prepares a FunctionPatcher for being inserted into another method
        Does the stuff around the control flow control methods
        Will work on a copy of the method, not the method itself
        """
        breakpoint()
        method = method.copy()

        i = 0
        helper = BytecodePatchHelper(method)

        while i < len(helper.instruction_listing):
            instr = helper.instruction_listing[i]

        return method

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
        self, index: int, offset: int
    ) -> typing.Iterator[dis.Instruction]:
        """
        Finds the source instruction of the given stack element.
        Uses advanced back-tracking in code

        :param index: current instruction index, before which we want to know the layout
        :param offset: the offset, where 0 is top, and all following numbers (1, 2, 3, ...) give the i+1-th
            element of the stack
        """

        self.re_eval_instructions()
        instructions = list(self.walk())
        # print(instructions)
        # print(index, offset)

        for index, instr in reversed(instructions[:index]):
            if offset < 0:
                raise RuntimeError(offset, instructions[index+1])

            # print(instr, offset)

            if offset == 0:  # Currently, at top
                if instr.opcode in LOAD_SINGLE_VALUE:
                    yield instr
                    return

                elif (
                    instr.opcode in POP_DOUBLE_AND_PUSH_SINGLE
                    or instr.opcode in POP_SINGLE_AND_PUSH_SINGLE
                ):
                    yield instr
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

            elif instr.opcode == METHOD_CALL:
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

            elif sys.version_info.major >= 3 and sys.version_info.minor >= 11 and instr.opcode == Opcodes.BINARY_OP:
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
