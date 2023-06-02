import copy
import dis
import sys
import types
import typing
import simplejson

from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import ArgRealValueSetter
from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import ExtendedArgInserter
from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import InstructionAssembler
from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import JumpArgAssembler
from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import LinearStreamGenerator
from bytecodemanipulation.opcodes.CodeObjectBuilder import CodeObjectBuilder
from bytecodemanipulation.opcodes.ExceptionTable import ExceptionTable
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import AbstractOpcodeTransformerStage, InstructionDecoder
from bytecodemanipulation.opcodes.Opcodes import (
    Opcodes,
)
import bytecodemanipulation.data_loader


class LinearCodeConstraintViolationException(Exception):
    pass


class MutableFunction:
    INSTRUCTION_DECODING_PIPE: typing.List[typing.Type[AbstractOpcodeTransformerStage]] = [
        InstructionDecoder,
    ]

    INSTRUCTION_ENCODING_PIPE: typing.List[typing.Type[AbstractOpcodeTransformerStage]] = [
        ArgRealValueSetter,
        ExtendedArgInserter,
        LinearStreamGenerator,
        JumpArgAssembler,
        InstructionAssembler,  # the last stage, assembling the instructions into real bytes
    ]

    @classmethod
    def create(cls, target):
        if isinstance(target, staticmethod):
            return cls(target.__func__)
        elif isinstance(target, classmethod):
            return cls(target.__func__)
        return cls(target)

    def __init__(self, target: types.FunctionType | types.MethodType):
        self.target = target
        self.code_object: types.CodeType = target.__code__

        self.__instructions: typing.Optional[typing.List[Instruction]] = None
        self._raw_code: bytearray = None

        self.argument_count = 0
        self.keyword_only_argument_count = 0
        self.positional_only_argument_count = 0

        self.filename: str | None = None
        self.function_name: str | None = None

        self.first_line_number = 0

        self.code_flags = 0

        # todo: fill out when decoding
        # todo: encode when encoding
        self.exception_table = ExceptionTable(self)

        self._load_from_code_object(self.code_object)

    if sys.version_info.major == 3 and sys.version_info.minor == 10:

        def _load_from_code_object(self, obj: types.CodeType):
            self.argument_count = self.code_object.co_argcount
            # self.cell_variables = list(self.code_object.co_cellvars)
            self._raw_code = bytearray(self.code_object.co_code)
            # self.constants = list(self.code_object.co_consts)
            self.filename = self.code_object.co_filename
            self.first_line_number = self.code_object.co_firstlineno
            self.code_flags = self.code_object.co_flags
            # self.free_variables = list(self.code_object.co_freevars)
            self.keyword_only_argument_count = self.code_object.co_kwonlyargcount
            # self.line_table = self.code_object.co_linetable
            # self.lnotab = bytearray(self.code_object.co_lnotab)

            self.function_name = self.code_object.co_name
            # self.shared_names = list(self.code_object.co_names)
            # Local variable count is implied by co_varnames
            self.positional_only_argument_count = self.code_object.co_posonlyargcount
            # self.stack_size = self.code_object.co_stacksize
            # self.shared_variable_names = list(self.code_object.co_varnames)

    elif sys.version_info.major == 3 and sys.version_info.minor == 11:

        def _load_from_code_object(self, obj: types.CodeType):
            self.argument_count = self.code_object.co_argcount
            # self.cell_variables = list(self.code_object.co_cellvars)
            self._raw_code = bytearray(self.code_object.co_code)
            # self.constants = list(self.code_object.co_consts)
            self.filename = self.code_object.co_filename
            self.first_line_number = self.code_object.co_firstlineno
            self.code_flags = self.code_object.co_flags
            # self.free_variables = list(self.code_object.co_freevars)
            self.keyword_only_argument_count = self.code_object.co_kwonlyargcount
            # self.line_table = self.code_object.co_linetable
            # self.lnotab = bytearray(self.code_object.co_lnotab)

            self.function_name = self.code_object.co_name
            # self.shared_names = list(self.code_object.co_names)
            # Local variable count is implied by co_varnames
            self.positional_only_argument_count = self.code_object.co_posonlyargcount
            # self.stack_size = self.code_object.co_stacksize
            # self.shared_variable_names = list(self.code_object.co_varnames)

            # self.exception_table = bytearray(self.code_object.co_exceptiontable)

            self.__instructions: typing.Optional[typing.List[Instruction]] = None

    else:
        raise RuntimeError(sys.version_info)

    def __repr__(self):
        return f"MutableFunction({self.target})"

    def copy(self):
        def _():
            pass

        instance = type(self)(_)
        instance.copy_from(self)

        return instance

    def copy_from(self, mutable: "MutableFunction"):
        # self.target = mutable.target
        self.code_object = mutable.code_object

        self.argument_count = mutable.argument_count
        self.cell_variables = mutable.cell_variables.copy()
        self._raw_code = mutable.raw_code.copy()
        self.constants = copy.deepcopy(mutable.constants)
        self.filename = mutable.filename
        self.first_line_number = mutable.first_line_number
        self.code_flags = mutable.code_flags
        self.free_variables = mutable.free_variables.copy()
        self.keyword_only_argument_count = mutable.keyword_only_argument_count
        self.line_table = copy.copy(mutable.line_table)
        self.lnotab = mutable.lnotab
        self.function_name = mutable.function_name
        self.shared_names = mutable.shared_names.copy()
        self.positional_only_argument_count = mutable.positional_only_argument_count
        self.stack_size = mutable.stack_size
        self.shared_variable_names = mutable.shared_variable_names.copy()

        self.__instructions = None

    if sys.version_info.major == 3 and sys.version_info.minor == 10:

        def create_code_obj(self) -> types.CodeType:
            if self.__instructions is None:
                self.get_instructions()

            builder = self.create_filled_builder()

            self.assemble_fast(self.__instructions)

            return types.CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                len(builder.shared_variable_names),
                self.stack_size,
                self.code_flags,
                bytes(self.raw_code),
                tuple(builder.constants),
                tuple(builder.shared_names),
                tuple(builder.shared_variable_names),
                self.filename,
                self.function_name,
                self.first_line_number,
                self.get_lnotab(),
                tuple(builder.free_variables),
                tuple(builder.cell_variables),
            )

    elif sys.version_info.major == 3 and sys.version_info.minor == 11:

        def create_code_obj(self) -> types.CodeType:
            if self.__instructions is None:
                self.get_instructions()

            self.assemble_fast(self.__instructions)

            return types.CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                len(self.shared_variable_names),
                self.stack_size,
                self.code_flags,
                bytes(self.raw_code),
                tuple(self.constants),
                tuple(self.shared_names),
                tuple(self.shared_variable_names),
                self.filename,
                self.function_name,
                self.function_name,
                self.first_line_number,
                self.get_lnotab(),
                bytes(self.exception_table),
                tuple(self.free_variables),
                tuple(self.cell_variables),
            )

    def get_lnotab(self) -> bytes:
        items = []

        prev_line = self.first_line_number
        count_since_previous = 0

        for instr in self.__instructions:
            count_since_previous += 1

            if instr.source_location is None or instr.source_location[0] == prev_line:
                continue

            offset = instr.source_location[0] - prev_line

            if offset > 127:
                return bytes()

            if offset < 0:
                return bytes()

            items.append(count_since_previous)
            items.append(offset)
            count_since_previous = 0

        return bytes(items)

    def calculate_max_stack_size(self) -> int:
        stack_size_table = self.get_max_stack_size_table()

        self.stack_size = max(max(stack_size_table), 0)
        return self.stack_size

    def get_max_stack_size_table(
        self, instructions: typing.List[Instruction] = None
    ) -> typing.List[int]:
        stack_size_table = [-1] * len(instructions or self.instructions)

        if not instructions:
            self.prepare_previous_instructions()

        for i, instr in enumerate(instructions or self.instructions):
            stack = -1
            if i != 0:
                prev = (instructions or self.instructions)[i - 1]

                if not prev.has_stop_flow() and not prev.has_unconditional_jump():
                    stack = stack_size_table[i - 1]
            else:
                stack = 0

            if instr.previous_instructions:
                for instruction in instr.previous_instructions:
                    if stack_size_table[instruction.offset] != -1:
                        stack = max(stack, stack_size_table[instruction.offset])
                        stack += instruction.special_stack_affect_when_followed_by(
                            instr
                        )

            if stack != -1:
                add, sub, _ = instr.get_stack_affect()
                stack += add
                stack -= sub

            stack_size_table[i] = stack

        if -1 in stack_size_table:
            pending = list(filter(lambda e: e[1] == -1, enumerate(stack_size_table)))
            last_next = -1

            while pending:
                i, _ = pending.pop(0)
                instr = (instructions or self.instructions)[i]
                stack = -1

                if i == last_next:
                    break

                if not instr.previous_instructions:
                    print("WARN:", instr)
                    continue

                for instruction in instr.previous_instructions:
                    if stack_size_table[instruction.offset] != -1:
                        stack = max(stack, stack_size_table[instruction.offset])
                        stack += instruction.special_stack_affect_when_followed_by(
                            instr
                        )

                if stack != -1:
                    add, sub, _ = instr.get_stack_affect()
                    stack += add
                    stack -= sub

                    stack_size_table[i] = stack

                    if pending:
                        last_next = pending[0][0]
                else:
                    pending.append((i, -1))

                if last_next == -1:
                    last_next = i

        return stack_size_table

    def reassign_to_function(self):
        self.calculate_max_stack_size()
        self.target.__code__ = self.create_code_obj()

    def decode_instructions(self):
        if self.__instructions is not None:
            self.__instructions.clear()
        else:
            self.__instructions = []

        metadata = None
        for stage in self.INSTRUCTION_DECODING_PIPE:
            metadata = stage.apply(self, metadata)

        self.prepare_previous_instructions()

    def create_filled_builder(self):
        builder = CodeObjectBuilder(self)

        for stage in self.INSTRUCTION_ENCODING_PIPE:
            stage.apply(self, builder)

        return builder

    def prepare_previous_instructions(self):
        for instruction in self.instructions:
            if instruction.previous_instructions:
                instruction.previous_instructions.clear()

        for instruction in self.instructions:
            if instruction.has_stop_flow() or instruction.has_unconditional_jump():
                continue

            instruction.next_instruction.add_previous_instruction(instruction)

            if instruction.has_jump():
                # print(instruction.arg_value, typing.cast, typing.cast(Instruction, instruction.arg_value))

                typing.cast(
                    Instruction, instruction.arg_value
                ).add_previous_instruction(instruction)

    def update_instruction_offsets(self, instructions):
        # Update instruction positions
        for i, instruction in enumerate(instructions):
            instruction.offset = i

    def assemble_fast(self, instructions: typing.List[Instruction]):
        """
        Assembles the instruction list in FAST mode
        Removes some safety checks, and removes the dynamic assemble_instructions_from_tree() forwarding.
        Requires the linking of instructions to be LINEAR.

        :raises ValueError: if not enough space for EXTENDED_ARG's is available
        """

        builder = CodeObjectBuilder(self)
        builder.temporary_instructions = instructions

        InstructionAssembler.apply(self, builder)

    def get_raw_code(self):
        if self.__instructions is not None:
            self.create_filled_builder()

        return self._raw_code

    def get_raw_code_unsafe(self):
        return self._raw_code

    def set_raw_code(self, raw_code: bytearray):
        self._raw_code = raw_code

        if self.__instructions is not None:
            self.decode_instructions()

    raw_code = property(get_raw_code, set_raw_code)

    def get_instructions(self):
        if self.__instructions is None:
            self.decode_instructions()

        return self.__instructions

    def set_instructions(self, instructions: typing.List[Instruction]):
        # Update the ownerships of the instructions, so they point to us now
        # todo: do we want to copy in some cases?
        self.__instructions = instructions
        self.__instructions = [
            instruction.update_owner(self, i, update_following=False)
            for i, instruction in enumerate(instructions)
        ]

        for i, instruction in enumerate(instructions[:-1]):
            if not instruction.has_stop_flow():
                instruction.set_next_instruction_unsafe(instructions[i+1])

    instructions = property(get_instructions, set_instructions)

    def dump_info(self, file: str):
        data = {
            "instructions": [
                {
                    "opcode": instr.opcode,
                    "opname": instr.opname,
                    "arg": instr.arg,
                    "arg_value": repr(instr.arg_value),
                    "offset": instr.offset,
                }
                for instr in self.instructions
            ]
        }

        with open(file, mode="w") as f:
            simplejson.dump(data, f, indent="  ")


bytecodemanipulation.data_loader.init()
