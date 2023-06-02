from abc import ABC
import typing

from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes

if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction


class AbstractOpcodeTransformerStage(ABC):
    @classmethod
    def apply(cls, function: "MutableFunction", metadata: typing.Any) -> typing.Any:
        raise NotImplementedError


class InstructionDecoder(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", metadata: typing.Any) -> typing.Any:
        line = function.first_line_number
        lnotab = list(function.lnotab)

        instructions = []

        extra: int = 0
        for i in range(0, len(function.get_raw_code_unsafe()), 2):
            opcode, arg = function.get_raw_code_unsafe()[i: i + 2]

            if opcode == Opcodes.EXTENDED_ARG:
                extra = extra * 256 + arg
                instr = Instruction(function, i // 2, "NOP", _decode_next=False)

            else:
                arg += extra * 256
                extra = 0

                if opcode in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                    arg += 1

                instr = Instruction(function, i // 2, opcode, arg=arg, _decode_next=False)

            if lnotab:
                lnotab[0] -= 1

                if lnotab[0] == 0:
                    line_incr = lnotab[1]
                    del lnotab[:2]

                    line += line_incr

            instr.source_location = (line, None, None)

            instructions.append(instr)

        function.set_instructions(instructions)


class InstructionEncoder(AbstractOpcodeTransformerStage):
    pass

