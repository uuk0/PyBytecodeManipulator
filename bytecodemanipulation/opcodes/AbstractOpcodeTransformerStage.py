import sys
from abc import ABC
import typing

from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes
from bytecodemanipulation.opcodes.CodeObjectBuilder import CodeObjectBuilder

if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction


class AbstractOpcodeTransformerStage(ABC):
    @classmethod
    def apply(cls, function: "MutableFunction", metadata: typing.Any) -> typing.Any:
        raise NotImplementedError


class InstructionDecoder(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", metadata: list) -> typing.Any:
        line = function.code_object.co_firstlineno
        lnotab = list(function.code_object.co_lnotab)

        instructions = []

        extra: int = 0
        for i in range(0, len(function.get_raw_code_unsafe()), 2):
            opcode, arg = function.get_raw_code_unsafe()[i: i + 2]

            if opcode == Opcodes.EXTENDED_ARG:
                extra = extra * 256 + arg
                instr = Instruction(Opcodes.NOP)
                instr.offset = i // 2

            else:
                arg += extra * 256
                extra = 0

                if opcode in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                    arg += 1

                instr = Instruction(opcode)
                instr.offset = i // 2

                if instr.has_local():
                    instr.arg_value = function.code_object.co_varnames[arg]
                elif sys.version_info[1] >= 11 and opcode == Opcodes.LOAD_GLOBAL:
                    instr.arg_value = function.code_object.co_names[arg >> 1]
                elif instr.has_name():
                    instr.arg_value = function.code_object.co_names[arg]
                elif instr.has_constant():
                    instr.arg_value = function.code_object.co_consts[arg]
                elif instr.has_cell_variable():
                    # todo: py-3.10 could need special handling here!
                    instr.arg_value = function.code_object.co_cellvars[arg]
                else:
                    instr.arg = arg

            if lnotab:
                lnotab[0] -= 1

                if lnotab[0] <= 0:
                    line_incr = lnotab[1]
                    del lnotab[:2]

                    line += line_incr

            instr.source_location = (line, None, None)
            instr.offset = i // 2

            instructions.append(instr)

        for instr in instructions:
            if instr.has_jump_absolute():
                instr.arg_value = instructions[instr.arg]
                instr.arg = None
            elif instr.has_jump_forward():
                instr.arg_value = instructions[instr.offset + instr.arg]
                instr.arg = None
            elif instr.has_jump_backward():
                instr.arg_value = instructions[instr.offset - instr.arg]
                instr.arg = None

        for i, instr in enumerate(instructions[:-1]):
            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                instr.next_instruction = instructions[i+1]

        function.instruction_entry_point = instructions[0]
        metadata[:] = instructions


class AbstractInstructionWalkerTransform(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", metadata: typing.Any):
        visiting = {function.get_instruction_entry_point()} | set(function.exception_table.table.keys())
        visited = set()

        while visiting:
            instr = visiting.pop()

            if instr in visited or instr is None:
                continue

            visited.add(instr)

            try:
                cls.visit(
                    function,
                    metadata,
                    instr,
                )
            except StopIteration:
                return

            if not instr.has_stop_flow() and not instr.has_unconditional_jump():
                visiting.add(instr.next_instruction)

            if instr.has_jump():
                visiting.add(instr.arg_value)

    @classmethod
    def get_handed_over_metadata(cls, function: "MutableFunction", metadata: typing.Any) -> typing.Any:
        return metadata

    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.Any, target: "Instruction") -> typing.Any:
        pass

    @classmethod
    def get_new_metadata(cls, function: "MutableFunction", old_meta: typing.Any, metadata: typing.List[typing.Tuple["Instruction", typing.Any]]) -> typing.Any:
        return old_meta


class ArgRealValueSetter(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", builder: CodeObjectBuilder, target: "Instruction") -> typing.Any:
        if target.has_local():
            target.arg = builder.reserve_local_name(target.arg_value)
        elif target.has_name():
            target.arg = builder.reserve_name(target.arg_value)
        elif target.has_cell_variable():
            target.arg = builder.reserve_cell_name(target.arg_value)
        elif target.has_constant():
            target.arg = builder.reserve_constant(target.arg_value)


class ExtendedArgInserter(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", builder: CodeObjectBuilder, target: "Instruction") -> typing.Any:
        if target.arg is not None and target.arg > 255:
            arg = target.arg
            target.arg = arg % 256
            arg //= 256

            while arg > 0:
                c = target.copy()
                c.arg = arg % 256
                arg //= 256

                if arg > 0:
                    target.insert_after(c)
                    target.change_opcode(Opcodes.EXTENDED_ARG)


class LinearStreamGenerator(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", builder: CodeObjectBuilder, breaks_flow=tuple()):

        # While we have branches, we need to decode them
        pending_instructions = {function.get_instruction_entry_point()} | set(function.exception_table.table.keys())
        visited: typing.Set[Instruction] = set()
        instructions: typing.List[Instruction] = []

        while pending_instructions:
            instruction = pending_instructions.pop()

            if not isinstance(instruction, Instruction):
                print(f"Invalid task instruction: {instruction}")
                continue

            if not isinstance(instruction, Instruction):
                raise ValueError(instruction)

            # If we visited it, we can skip
            if instruction in visited:
                continue

            # Walk over the instructions as long as we have not met them
            while instruction not in visited:
                if not isinstance(instruction, Instruction):
                    print(f"Invalid task instruction: {instruction}")
                    break

                # If it branches off, it needs to be visited later on
                if instruction.has_jump():
                    assert instruction.arg_value is not None, instruction

                    pending_instructions.add(instruction.arg_value)

                instructions.append(instruction)
                visited.add(instruction)

                if (
                    instruction.has_stop_flow()
                    or instruction in breaks_flow
                    or instruction.opcode in breaks_flow
                    or instruction.has_unconditional_jump()
                ):
                    break

                # The next instruction MUST be set if it does NOT end the control flow
                if instruction.next_instruction is None:
                    print("---- start dump")
                    for instr in instructions:
                        print(instr)
                    print("---- end dump")
                    raise RuntimeError(f"next instruction is None: {instruction}")

                instruction = instruction.next_instruction

        builder.temporary_instructions[:] = instructions


class JumpArgAssembler(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", builder: CodeObjectBuilder):
        cls.insert_needed_jumps(function, builder)

        cls.update_jump_args(function, builder)

        function.set_instruction_entry_point(builder.temporary_instructions[0])
        ExtendedArgInserter.apply(function, builder)
        LinearStreamGenerator.apply(function, builder)

    @classmethod
    def insert_needed_jumps(cls, function: "MutableFunction", builder: CodeObjectBuilder):
        for i, instruction in enumerate(builder.temporary_instructions):
            instruction.offset = i

        # Check for unconditional jumps required
        for instruction in builder.temporary_instructions[:]:
            if instruction.has_stop_flow() or instruction.has_unconditional_jump():
                continue

            # FOR_ITER can only jump FORWARD, so insert a new jump absolute to jump there
            # TODO: insert the JUMP somewhere else than here!
            if instruction.opcode == Opcodes.FOR_ITER:
                jump = Instruction(
                    Opcodes.JUMP_ABSOLUTE,
                    instruction.next_instruction,
                )
                jump.change_arg_value(instruction.arg_value)
                instruction.change_arg_value(jump)
                builder.temporary_instructions.append(jump)

            if (
                instruction.next_instruction is not None
                and instruction.offset + 1 != instruction.next_instruction.offset
            ):
                jump = Instruction(
                    Opcodes.JUMP_ABSOLUTE,
                    instruction.next_instruction,
                )
                jump.next_instruction = instruction
                instruction.next_instruction = jump
                builder.temporary_instructions.insert(builder.temporary_instructions.index(instruction) + 1, jump)

        for i, instruction in enumerate(builder.temporary_instructions):
            instruction.offset = i

    @classmethod
    def update_jump_args(cls, function: "MutableFunction", builder: CodeObjectBuilder):
        # Update the raw arg for jumps
        for i, instruction in enumerate(builder.temporary_instructions):
            if instruction.next_instruction is None:
                continue

            if instruction.has_jump_absolute():
                instruction.change_arg(instruction.arg_value.offset)

            elif instruction.opcode in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                instruction.change_arg(instruction.arg_value.offset - instruction.offset - 2)

            elif instruction.has_jump_forward():
                instruction.change_arg(instruction.arg_value.offset - instruction.offset)

            elif instruction.has_jump_backward():
                instruction.change_arg(instruction.offset - instruction.arg_value.offset)


class InstructionAssembler(AbstractOpcodeTransformerStage):
    """
    Transforms a linearised instruction stream into a bytearray
    """

    @classmethod
    def apply(cls, function: "MutableFunction", builder: CodeObjectBuilder):
        function.instruction_entry_point = builder.temporary_instructions[0]

        function._raw_code.clear()
        for i, instruction in enumerate(builder.temporary_instructions):
            if instruction.opcode > 255:
                raise ValueError(f"invalid instruction at result level: {instruction}")

            arg = instruction.get_arg()

            if instruction.opcode == Opcodes.SETUP_FINALLY:
                arg += 1

            if arg > 255:
                extend = arg // 256
                arg %= 256

                offset = 1
                while extend > 0:
                    iarg = extend % 256
                    extend //= 256

                    if function._raw_code[(i - offset) * 2] != Opcodes.NOP:
                        raise ValueError(
                            f"Cannot assemble fast, not enough NOP's for instruction {instruction}"
                        )

                    function._raw_code[(i - offset) * 2: (i - offset + 1) * 2] = bytes(
                        [Opcodes.EXTENDED_ARG, iarg]
                    )
                    offset += 1

            if not (0 <= arg <= 255 and 0 <= instruction.opcode <= 255):
                print("error", instruction)

                print("----")

                for ins in builder.temporary_instructions:
                    print(repr(ins))

                print("----")

            function._raw_code += bytes([instruction.opcode, arg])

