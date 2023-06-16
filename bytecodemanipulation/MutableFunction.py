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
import bytecodemanipulation.data_loader
from bytecodemanipulation.opcodes.OpcodeReplacer import IntermediateToRawOpcodeTransform
from bytecodemanipulation.opcodes.OpcodeReplacer import RawToIntermediateOpcodeTransform


class LinearCodeConstraintViolationException(Exception):
    pass


class MutableFunction:
    INSTRUCTION_DECODING_PIPE: typing.List[typing.Type[AbstractOpcodeTransformerStage]] = [
        InstructionDecoder,
        RawToIntermediateOpcodeTransform,
    ]

    if sys.version_info[1] == 10:
        from bytecodemanipulation.data.v3_10.ExceptionInstructionCodec import ExceptionInstructionDecoder
        from bytecodemanipulation.data.v3_10.LocationInformationHandler import LocationInformationDecoder

        INSTRUCTION_DECODING_PIPE += [
            ExceptionInstructionDecoder,
            LocationInformationDecoder,
        ]

    INSTRUCTION_ENCODING_PIPE: typing.List[typing.Type[AbstractOpcodeTransformerStage]] = [
        IntermediateToRawOpcodeTransform,
    ]

    if sys.version_info[1] == 10:
        from bytecodemanipulation.data.v3_10.ExceptionInstructionCodec import ExceptionInstructionEncoder

        INSTRUCTION_ENCODING_PIPE += [
            ExceptionInstructionEncoder,
        ]

    elif sys.version_info[1] == 11:
        from bytecodemanipulation.opcodes.CacheEntryCreation import CacheInstructionCreator
        from bytecodemanipulation.opcodes.OpcodeReplacer import PrecallInserterTransform

        INSTRUCTION_ENCODING_PIPE += [
            CacheInstructionCreator,
            PrecallInserterTransform,
        ]

    INSTRUCTION_ENCODING_PIPE += [
        ArgRealValueSetter,
        ExtendedArgInserter,
        LinearStreamGenerator,
        JumpArgAssembler,
    ]

    if sys.version_info[1] == 10:
        from bytecodemanipulation.data.v3_10.LocationInformationHandler import LocationInformationEncoder

        INSTRUCTION_ENCODING_PIPE += [
            LocationInformationEncoder,
        ]

    INSTRUCTION_ENCODING_PIPE += [
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

        self._raw_code: bytearray = None

        self.argument_names: typing.List[str] = None
        self.argument_count = 0
        self.keyword_only_argument_count = 0
        self.positional_only_argument_count = 0

        self.filename: str | None = None
        self.function_name: str | None = None

        self.code_flags = 0

        self._instruction_entry_point: Instruction = None

        self.exception_table = ExceptionTable(self)

        self._load_from_code_object(self.code_object)

    if sys.version_info.major == 3 and sys.version_info.minor == 10:

        def _load_from_code_object(self, obj: types.CodeType):
            self.argument_count = obj.co_argcount
            self._raw_code = bytearray(obj.co_code)
            self.filename = obj.co_filename
            self.code_flags = obj.co_flags
            self.keyword_only_argument_count = obj.co_kwonlyargcount

            self.function_name = obj.co_name
            self.positional_only_argument_count = obj.co_posonlyargcount
            self.argument_names = list(obj.co_varnames[:self.argument_count])

    elif sys.version_info.major == 3 and sys.version_info.minor == 11:

        def _load_from_code_object(self, obj: types.CodeType):
            self.argument_count = obj.co_argcount
            self._raw_code = bytearray(obj.co_code)
            self.filename = obj.co_filename
            self.code_flags = obj.co_flags
            self.keyword_only_argument_count = obj.co_kwonlyargcount

            # self.line_table = obj.co_linetable
            # self.lnotab = bytearray(obj.co_lnotab)

            self.function_name = obj.co_name
            self.positional_only_argument_count = obj.co_posonlyargcount
            self.argument_names = list(obj.co_varnames[:self.argument_count])

            # self.exception_table = bytearray(obj.co_exceptiontable)

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

    def deep_copy(self):
        instance = self.copy()

        copied = {}
        instance._instruction_entry_point = instance._instruction_entry_point.copy_deep(copied)

        return instance

    def copy_from(self, mutable: "MutableFunction"):
        # self.target = mutable.target
        self.code_object = mutable.code_object

        self.argument_count = mutable.argument_count
        # self.cell_variables = mutable.cell_variables.copy()
        self._raw_code = mutable.raw_code.copy()
        # self.constants = copy.deepcopy(mutable.constants)
        self.filename = mutable.filename
        self.code_flags = mutable.code_flags
        # self.free_variables = mutable.free_variables.copy()
        self.keyword_only_argument_count = mutable.keyword_only_argument_count
        # self.line_table = copy.copy(mutable.line_table)
        # self.lnotab = mutable.lnotab
        self.function_name = mutable.function_name
        # self.shared_names = mutable.shared_names.copy()
        self.positional_only_argument_count = mutable.positional_only_argument_count
        # self.stack_size = mutable.stack_size
        # self.shared_variable_names = mutable.shared_variable_names.copy()

        self.instruction_entry_point = mutable.instruction_entry_point

    if sys.version_info.major == 3 and sys.version_info.minor == 10:

        def create_code_obj(self) -> types.CodeType:
            builder = self.create_filled_builder()

            self.prepare_previous_instructions()

            try:
                return types.CodeType(
                    self.argument_count,
                    self.positional_only_argument_count,
                    self.keyword_only_argument_count,
                    len(builder.shared_variable_names),
                    self.calculate_max_stack_size(),
                    self.code_flags,
                    bytes(self.raw_code),
                    tuple(builder.constants),
                    tuple(builder.shared_names),
                    tuple(builder.shared_variable_names),
                    self.filename,
                    self.function_name,
                    builder.first_line_number,
                    builder.line_info_table,
                    tuple(builder.free_variables),
                    tuple(builder.cell_variables),
                )
            except:
                print(builder.shared_variable_names)
                print(len(builder.shared_variable_names))

                for i in range(0, len(self.raw_code), 2):
                    frag = self.raw_code[i:i+2]
                    print(tuple(frag))

                self.walk_instructions(lambda instr: print(instr))

                print(self)
                raise

    elif sys.version_info.major == 3 and sys.version_info.minor == 11:

        def create_code_obj(self) -> types.CodeType:
            builder = self.create_filled_builder()

            self.prepare_previous_instructions()

            return types.CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                len(builder.shared_variable_names),
                self.calculate_max_stack_size(),
                self.code_flags,
                bytes(self.raw_code),
                tuple(builder.constants),
                tuple(builder.shared_names),
                tuple(builder.shared_variable_names),
                self.filename,
                self.function_name,
                self.function_name,
                builder.first_line_number,
                builder.line_info_table,
                bytes(),  # todo: encode
                tuple(builder.free_variables),
                tuple(builder.cell_variables),
            )

    def calculate_max_stack_size(self) -> int:
        normal_max = self._calculate_max_stack_size_normal_path()

        if len(self.exception_table.table) == 0:
            return normal_max

        def reset(instr: Instruction):
            instr._max_stack_size_at = -1

        self.walk_instructions(reset)

        visiting = {self.get_instruction_entry_point()} | set(self.exception_table.table.keys())
        visiting_2 = set()
        visited = set()

        for instr in visiting:
            instr._max_stack_size_at = 0

        while visiting or visiting_2:
            if not visiting:
                visiting |= visiting_2
                visiting_2.clear()

            instr = visiting.pop()

            if instr in visited or instr is None:
                continue

            visited.add(instr)

            stack_size = 0
            previous = instr.previous_instructions
            needs_revisit = False

            for pinstr in previous:
                if pinstr._max_stack_size_at != -1:
                    psize = pinstr._max_stack_size_at
                    psize += pinstr.special_stack_affect_when_followed_by(instr)
                    pushed, popped, _ = pinstr.get_stack_affect()
                    psize += pushed
                    psize -= popped

                    stack_size = max(stack_size, psize)
                else:
                    needs_revisit = True

            if instr in self.exception_table.table:
                stack_size = max(stack_size, normal_max)

            instr._max_stack_size_at = stack_size

            if needs_revisit:
                visited.remove(instr)
                visiting_2.add(instr)

            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                visiting.add(instr.next_instruction)

            if instr.has_jump():
                visiting.add(instr.arg_value)

        stack_size = 0

        def visit(instr: Instruction):
            nonlocal stack_size
            stack_size = max(stack_size, instr._max_stack_size_at)

        self.walk_instructions(visit)

        return stack_size

    def _calculate_max_stack_size_normal_path(self) -> int:
        def reset(instr: Instruction):
            instr._max_stack_size_at = -1

        self.walk_instructions(reset)

        visiting = {self.get_instruction_entry_point()}
        visiting_2 = set()
        visited = set()

        for instr in visiting:
            instr._max_stack_size_at = 0

        while visiting or visiting_2:
            if not visiting:
                visiting |= visiting_2
                visiting_2.clear()

            instr = visiting.pop()

            if instr in visited or instr is None:
                continue

            visited.add(instr)

            stack_size = 0
            previous = instr.previous_instructions
            needs_revisit = False

            for pinstr in previous:
                if pinstr._max_stack_size_at != -1:
                    psize = pinstr._max_stack_size_at
                    psize += pinstr.special_stack_affect_when_followed_by(instr)
                    pushed, popped, _ = pinstr.get_stack_affect()
                    psize += pushed
                    psize -= popped

                    stack_size = max(stack_size, psize)
                else:
                    needs_revisit = True

            instr._max_stack_size_at = stack_size

            if needs_revisit:
                visited.remove(instr)
                visiting_2.add(instr)

            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                visiting.add(instr.next_instruction)

            if instr.has_jump():
                visiting.add(instr.arg_value)

        stack_size = 0

        def visit(instr: Instruction):
            nonlocal stack_size
            stack_size = max(stack_size, instr._max_stack_size_at)

        self.walk_instructions(visit)

        return stack_size

    def walk_instructions(self, callback: typing.Callable[[Instruction], None], include_exception_entries=True):
        """
        Walks the graph of instructions, visiting all "reachable" instructions
        in the function

        WARNING: mutating the graph in the callback MIGHT result in bad behaviour,
        depending on what the 'callback' does exactly, as 'callback' might
        be invoked on newly inserted instructions.

        :param callback: the callback to use, invoked with each reachable instruction
            (might raise StopIteration to stop further callbacks from happening)
        :param include_exception_entries: if True, the entries defined in the exception table
            will be also used
        """
        visiting = {self.get_instruction_entry_point()}

        if include_exception_entries:
            visiting |= set(self.exception_table.table.keys())
        
        visited = set()

        while visiting:
            instr = visiting.pop()

            if instr in visited or instr is None or not isinstance(instr, Instruction):
                continue

            visited.add(instr)

            try:
                callback(instr)
            except StopIteration:
                return

            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                visiting.add(instr.next_instruction)

            if instr.has_jump():
                visiting.add(instr.arg_value)

    def walk_instructions_stable(self, callback: typing.Callable[[Instruction], None], include_exception_entries=True):
        """
        "Stable" variant of walk_instructions()
        Allows <param>.insert_after() to be called without recursion happening

        :param callback: the callback to call
            (might raise StopIteration to stop further callbacks from happening)
        :param include_exception_entries: if True, the entries defined in the exception table
            will be also used
        """
        visiting = {self.get_instruction_entry_point()}

        if include_exception_entries:
            visiting |= set(self.exception_table.table.keys())

        visited = set()

        while visiting:
            instr = visiting.pop()

            if instr in visited or instr is None or not isinstance(instr, Instruction):
                continue

            visited.add(instr)

            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                visiting.add(instr.next_instruction)

            if instr.has_jump():
                visiting.add(instr.arg_value)

            try:
                callback(instr)
            except StopIteration:
                return

    def reassign_to_function(self):
        self.prepare_previous_instructions()
        self.calculate_max_stack_size()
        self.target.__code__ = self.create_code_obj()

    def decode_instructions(self):
        metadata = []

        for stage in self.INSTRUCTION_DECODING_PIPE:
            stage.apply(self, metadata)

        self.instruction_entry_point = self.instruction_entry_point.optimise_tree()
        self.prepare_previous_instructions()

    def prepare_previous_instructions(self):
        def clear(instr: Instruction):
            if instr.previous_instructions:
                instr.previous_instructions.clear()
            else:
                instr.previous_instructions = []

        def callback(instr: Instruction):
            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                if instr.next_instruction is None:
                    raise RuntimeError(f"no next_instruction for {instr}")

                instr.next_instruction.previous_instructions.append(instr)

            if instr.has_jump():
                typing.cast(Instruction, instr.arg_value).previous_instructions.append(instr)

        self.walk_instructions(clear)
        self.walk_instructions(callback)

    def create_filled_builder(self, builder=None):
        builder = builder or CodeObjectBuilder(self)
        self.instruction_entry_point = self.instruction_entry_point.optimise_tree()

        for stage in self.INSTRUCTION_ENCODING_PIPE:
            stage.apply(self, builder)

        self.instruction_entry_point = self.instruction_entry_point.optimise_tree()

        meta = []
        for stage in self.INSTRUCTION_DECODING_PIPE:
            if stage != InstructionDecoder:
                stage.apply(self, meta)

        self.prepare_previous_instructions()

        return builder

    def get_instruction_entry_point(self):
        if self._instruction_entry_point is None:
            self.decode_instructions()

        return self._instruction_entry_point

    def set_instruction_entry_point(self, entry_point: Instruction):
        self._instruction_entry_point = entry_point

    instruction_entry_point = property(get_instruction_entry_point, set_instruction_entry_point)

    def assemble_fast(self, instructions: typing.List[Instruction]):
        """
        Assembles the instruction list in FAST mode
        Removes some safety checks, and removes the dynamic assemble_instructions_from_tree() forwarding.
        Requires the linking of instructions to be LINEAR.

        :raises ValueError: if not enough space for EXTENDED_ARG's is available
        """

        if not instructions:
            raise ValueError("<instructions> is empty!")

        builder = CodeObjectBuilder(self)
        builder.temporary_instructions = instructions

        InstructionAssembler.apply(self, builder)

    def get_raw_code(self):
        self.create_filled_builder()

        return self._raw_code

    def get_raw_code_unsafe(self):
        return self._raw_code

    def set_raw_code(self, raw_code: bytearray):
        self._raw_code = raw_code

        self.decode_instructions()

    raw_code = property(get_raw_code, set_raw_code)

    def dump_info(self, file: str):
        entries = []

        def visit(instr):
            entries.append(
                {
                    "opcode": instr.opcode,
                    "opname": instr.opname,
                    "arg": instr.arg,
                    "arg_value": repr(instr.arg_value),
                    "offset": instr.offset,
                }
            )

        self.walk_instructions(visit)

        data = {"instructions": entries}

        with open(file, mode="w") as f:
            simplejson.dump(data, f, indent="  ")


bytecodemanipulation.data_loader.init()
