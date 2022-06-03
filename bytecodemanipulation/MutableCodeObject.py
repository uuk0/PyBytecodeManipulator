import dis
import inspect
import itertools
import sys
import types
from types import CodeType, FunctionType

__all__ = ["MutableCodeObject"]

import typing

from bytecodemanipulation.util import OPCODE_NAMES
from bytecodemanipulation.util import Opcodes


def null():
    pass


def createInstruction(instruction: typing.Union[str, int], arg=0, argval=None):
    return dis.Instruction(
        instruction if isinstance(instruction, str) else OPCODE_NAMES[instruction],
        dis.opmap[instruction] if isinstance(instruction, str) else instruction,
        arg,
        argval,
        "" if argval is None else repr(argval),
        0,
        0,
        False,
    )


class MutableCodeObject:
    """
    Code inspired by https://rushter.com/blog/python-bytecode-patch/

    Wrapped class for handling __code__ objects at runtime,
    and writing the modified code back into the source function

    See https://docs.python.org/3.10/library/inspect.html
    and https://docs.python.org/3.10/library/dis.html
    """

    @classmethod
    def from_function(cls, target: FunctionType) -> "MutableCodeObject":
        obj = cls()
        obj.target = target
        obj.code = code = target.__code__

        code: types.CodeType

        obj.argument_count = code.co_argcount
        obj.positional_only_argument_count = code.co_posonlyargcount
        obj.keyword_only_argument_count = code.co_kwonlyargcount
        obj.number_of_locals = code.co_nlocals
        obj.max_stack_size = code.co_stacksize
        obj.flags = code.co_flags
        obj.code_string = bytearray(code.co_code)
        obj.constants = list(code.co_consts)
        obj.names = list(code.co_names)
        obj.variable_names = list(code.co_varnames)
        obj.filename = code.co_filename
        obj.name = code.co_name
        obj.first_line_number = code.co_firstlineno
        obj.line_number_table = code.co_lnotab
        obj.free_vars = list(code.co_freevars)
        obj.cell_vars = list(code.co_cellvars)

        if sys.version_info.minor >= 11 or typing.TYPE_CHECKING:
            obj.column_table = code.co_columntable
            obj.exception_table = code.co_exceptiontable
            obj.end_line_table = code.co_endlinetable
            obj.qual_name = code.co_qualname

        obj.parameters = inspect.signature(target).parameters.values()
        obj.func_defaults = list(
            filter(
                lambda e: e != inspect._empty, map(lambda e: e.default, obj.parameters)
            )
        )

        obj.can_be_reattached = True
        return obj

    def __init__(self):
        self.target: FunctionType = None
        self.code: types.CodeType = None

        # Number of real arguments, neither positional only nor keyword arguments
        self.argument_count = 0

        self.positional_only_argument_count = 0
        self.keyword_only_argument_count = 0
        self.number_of_locals = 0
        self.max_stack_size = 0

        # Code flags, see https://docs.python.org/3.10/library/inspect.html#inspect-module-co-flags
        self.flags = 0

        # The code string, transformed to a bytearray for manipulation
        self.code_string = bytearray()

        # The constants in the code, use ensureConstant when wanting new ones
        self.constants = []

        # The local variable name table
        self.names = []
        self.variable_names = []
        self.filename = __file__
        self.name = "unknown"
        self.first_line_number = 0
        self.line_number_table = b""
        self.free_vars = []
        self.cell_vars = []

        self.can_be_reattached = False

        self.parameters = []
        self.func_defaults = []

        if sys.version_info.minor >= 11 or typing.TYPE_CHECKING:
            self.column_table = None
            self.exception_table = None
            self.end_line_table = None
            self.qual_name = None

    def create_default_write_opcodes(
        self, total_previous_args: int, ensure_target: "MutableCodeObject" = None, prefix=""
    ) -> typing.Tuple[dis.Instruction]:
        if ensure_target is None:
            ensure_target = self

        count = min(len(self.func_defaults), self.argument_count - total_previous_args)
        head = len(self.func_defaults) - count

        # print(count, head, self.func_defaults, self.target, ensure_target.target)
        # print(self.variable_names[:self.argument_count][-count:])

        return sum(
            [
                (ensure_target.createLoadConst(e), ensure_target.createStoreFast(prefix+name))
                for e, name in zip(
                    self.func_defaults[head:],
                    self.variable_names[: self.argument_count][-count:],
                )
            ],
            tuple(),
        )

    if sys.version_info.minor <= 10:

        def applyPatches(self):
            """
            Writes the data this container holds back to the function
            """

            if not self.can_be_reattached:
                raise RuntimeError(
                    "Cannot reattach code object; Number of cell / free vars changed!"
                )

            self.target.__code__ = CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                self.number_of_locals,
                self.max_stack_size,
                self.flags,
                bytes(self.code_string),
                tuple(self.constants),
                tuple(self.names),
                tuple(self.variable_names),
                self.filename,
                self.name,
                self.first_line_number,
                self.line_number_table,
                tuple(self.free_vars),
                tuple(self.cell_vars),
            )
            self.target.func_defaults = self.func_defaults

    elif sys.version_info.minor == 11:

        def applyPatches(self):
            """
            Writes the data this container holds back to the function
            """

            if not self.can_be_reattached:
                raise RuntimeError(
                    "Cannot reattach code object; Number of cell / free vars changed!"
                )

            self.target.__code__ = CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                len(self.variable_names),
                self.max_stack_size,
                self.flags,
                bytes(self.code_string),
                tuple(self.constants),
                tuple(self.names),
                tuple(self.variable_names),
                self.filename,
                self.name,
                self.qual_name,
                self.first_line_number,
                self.line_number_table,
                self.end_line_table,
                self.column_table,
                self.exception_table,
                tuple(self.free_vars),
                tuple(self.cell_vars),
            )

    else:
        raise RuntimeError()

    if sys.version_info.minor <= 10:

        def create_method_from(self):
            return FunctionType(
                CodeType(
                    self.argument_count,
                    self.positional_only_argument_count,
                    self.keyword_only_argument_count,
                    self.number_of_locals,
                    self.max_stack_size,
                    self.flags,
                    bytes(self.code_string),
                    tuple(self.constants),
                    tuple(self.names),
                    tuple(self.variable_names),
                    self.filename,
                    self.name,
                    self.first_line_number,
                    self.line_number_table,
                    tuple(self.free_vars),
                    tuple(self.cell_vars),
                ),
                globals(),
            )

    elif sys.version_info.minor == 11:

        def create_method_from(self):
            return FunctionType(
                CodeType(
                    self.argument_count,
                    self.positional_only_argument_count,
                    self.keyword_only_argument_count,
                    len(self.variable_names),
                    self.max_stack_size,
                    self.flags,
                    bytes(self.code_string),
                    tuple(self.constants),
                    tuple(self.names),
                    tuple(self.variable_names),
                    self.filename,
                    self.name,
                    self.qual_name,
                    self.first_line_number,
                    self.line_number_table,
                    self.end_line_table,
                    self.column_table,
                    self.exception_table,
                    tuple(self.free_vars),
                    tuple(self.cell_vars),
                ),
                globals(),
            )

    else:
        raise RuntimeError()

    def overrideFrom(self, patcher: "MutableCodeObject"):
        """
        Force-overrides the content of this patcher with the one from another one
        """
        self.argument_count = patcher.argument_count
        self.positional_only_argument_count = patcher.positional_only_argument_count
        self.keyword_only_argument_count = patcher.keyword_only_argument_count
        self.number_of_locals = patcher.number_of_locals
        self.max_stack_size = patcher.max_stack_size
        self.flags = patcher.flags
        self.code_string = patcher.code_string
        self.constants = patcher.constants
        self.names = patcher.names
        self.variable_names = patcher.variable_names
        self.first_line_number = patcher.first_line_number
        self.line_number_table = patcher.line_number_table
        self.free_vars = patcher.free_vars
        self.cell_vars = patcher.cell_vars

        if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
            self.column_table = patcher.column_table
            self.exception_table = patcher.exception_table
            self.end_line_table = patcher.end_line_table
            self.qual_name = patcher.qual_name

        return self

    def copy(self):
        """
        Creates a copy of this object WITHOUT method binding
        Sets can_be_reattached simply to False
        """
        obj = MutableCodeObject.from_function(self.target)
        obj.overrideFrom(self)
        obj.can_be_reattached = False
        return obj

    def get_name_by_index(self, index: int):
        if index < len(self.variable_names):
            return self.variable_names[index]

        index -= len(self.variable_names)
        if index < len(self.cell_vars):
            return self.cell_vars[index]

        index -= len(self.cell_vars)
        if index < len(self.free_vars):
            return self.free_vars[index]

        raise IndexError(index)

    if sys.version_info.major >= 3 and sys.version_info.minor >= 11:

        def get_instruction_list(self) -> typing.List[dis.Instruction]:
            data = list(
                dis._get_instructions_bytes(
                    self.code_string,
                    self.get_name_by_index,
                    self.names,
                    self.constants,
                    None,
                    None,
                )
            )
            return data

    else:

        def get_instruction_list(self) -> typing.List[dis.Instruction]:
            return dis._get_instructions_bytes(
                self.code_string,
                self.variable_names,
                self.names,
                self.constants,
                self.cell_vars + self.free_vars,
            )

    def instructionList2Code(self, instruction_list: typing.List[dis.Instruction], helper=None):
        self.code_string.clear()

        from bytecodemanipulation.TransformationHelper import rebind_instruction_from_insert

        new_instructions = []

        if helper is None:
            from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
            helper = BytecodePatchHelper(self)

        skipped = 0

        for index, instr in enumerate(instruction_list):
            if instr.opname == "EXTENDED_ARG":
                skipped += 1
                continue

            if instr.arg is not None and instr.arg >= 256:
                if instr.arg >= 256 * 256:
                    if instr.arg >= 256 * 256 * 256:
                        data = instr.arg.to_bytes(4, "big", signed=False)
                    else:
                        data = instr.arg.to_bytes(3, "big", signed=False)
                else:
                    data = instr.arg.to_bytes(2, "big", signed=False)

                for delta, e in enumerate(data[:-1]):
                    new_instructions.append(
                        (
                            dis.Instruction(
                                "EXTENDED_ARG",
                                144,
                                e,
                                e,
                                "",
                                index - (len(data) - delta),
                                None,
                                False,
                            )
                        )
                    )

                if len(data) != skipped + 1:
                    if len(data) > skipped + 1:
                        helper.insertRegion(index, [createInstruction("EXTENDED_ARG") for _ in range(len(data) - skipped - 1)])
                        for i, instr2 in enumerate(new_instructions):
                            new_instructions[i] = rebind_instruction_from_insert(instr2, index, len(data) - skipped - 1)

                        for i, instr2 in itertools.dropwhile(lambda a, b: a <= index, enumerate(instruction_list)):
                            instruction_list[i] = rebind_instruction_from_insert(instr2, index, len(data) - skipped - 1)
                    else:
                        # todo: implement instruction offset remap
                        raise NotImplementedError(data, skipped)

            if skipped:
                skipped = 0

            new_instructions.append(instr)

        for instr in new_instructions:
            try:
                if instr.opcode > 255:
                    raise ValueError(instr)

                self.code_string.append(instr.opcode)

                if instr.arg is not None:
                    self.code_string.append(instr.arg % 256)
                else:
                    self.code_string.append(0)

            except:
                print(instr)
                raise

    def ensureConstant(self, const) -> int:
        """
        Makes some constant arrival in the program
        :param const: the constant
        :return: the index into the constant table
        """

        if const in self.constants:
            return self.constants.index(const)

        self.constants.append(const)
        return len(self.constants) - 1

    def createLoadConst(self, const):
        return dis.Instruction(
            "LOAD_CONST",
            Opcodes.LOAD_CONST,
            self.ensureConstant(const),
            const,
            repr(const),
            0,
            0,
            False,
        )

    def ensureName(self, name: str) -> int:
        if name in self.names:
            return self.names.index(name)

        self.names.append(name)
        return len(self.names) - 1

    def createLoadName(self, name: str):
        return dis.Instruction(
            "LOAD_NAME",
            Opcodes.LOAD_NAME,
            self.ensureName(name),
            name,
            name,
            0,
            0,
            False,
        )

    def createStoreName(self, name: str):
        return dis.Instruction(
            "STORE_NAME",
            Opcodes.STORE_NAME,
            self.ensureName(name),
            name,
            name,
            0,
            0,
            False,
        )

    def createLoadGlobal(self, name: str):
        return dis.Instruction(
            "LOAD_GLOBAL",
            Opcodes.LOAD_GLOBAL,
            self.ensureName(name),
            name,
            name,
            0,
            0,
            False,
        )

    def createStoreGlobal(self, name: str):
        return dis.Instruction(
            "STORE_GLOBAL",
            Opcodes.STORE_GLOBAL,
            self.ensureName(name),
            name,
            name,
            0,
            0,
            False,
        )

    def ensureVarName(self, name):
        if name in self.variable_names:
            return self.variable_names.index(name)

        self.variable_names.append(name)
        return len(self.variable_names) - 1

    def createLoadFast(self, name: str):
        return dis.Instruction(
            "LOAD_FAST",
            Opcodes.LOAD_FAST,
            self.ensureVarName(name),
            name,
            name,
            0,
            0,
            False,
        )

    def createStoreFast(self, name: str):
        return dis.Instruction(
            "STORE_FAST",
            Opcodes.STORE_FAST,
            self.ensureVarName(name),
            name,
            name,
            0,
            0,
            False,
        )

    def ensureFreeVar(self, name: str):
        if name in self.free_vars:
            return self.free_vars.index(name)
        self.free_vars.append(name)
        self.can_be_reattached = False
        return len(self.free_vars) - 1

    def ensureCellVar(self, name: str):
        if name in self.cell_vars:
            return self.cell_vars.index(name)
        self.cell_vars.append(name)
        self.can_be_reattached = False
        return len(self.cell_vars) - 1
