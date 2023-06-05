import typing

from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import AbstractInstructionWalkerTransform
from bytecodemanipulation.opcodes.Opcodes import Opcodes

if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction
    from bytecodemanipulation.opcodes.Instruction import Instruction


from bytecodemanipulation.data_loader import load_opcode_data

load_opcode_data()


OPCODE_DATA = [
    ((Opcodes.COMPARE_OP, 0), Opcodes.COMPARE_LT),
    ((Opcodes.COMPARE_OP, 1), Opcodes.COMPARE_LE),
    ((Opcodes.COMPARE_OP, 2), Opcodes.COMPARE_EQ),
    ((Opcodes.COMPARE_OP, 3), Opcodes.COMPARE_NEQ),
    ((Opcodes.COMPARE_OP, 4), Opcodes.COMPARE_GT),
    ((Opcodes.COMPARE_OP, 5), Opcodes.COMPARE_GE),
]

FORWARD_MAP = {e[0]: e[1] for e in OPCODE_DATA}
REVERSE_MAP = {e[1]: e[0] for e in OPCODE_DATA}


class RawToIntermediateOperatorTransform(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.Any, target: "Instruction") -> typing.Any:
        if (target.opcode, target.arg) in FORWARD_MAP:
            target.change_opcode(FORWARD_MAP[(target.opcode, target.arg)])


class IntermediateToRawOperatorTransform(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.Any, target: "Instruction") -> typing.Any:
        if target.opcode in REVERSE_MAP:
            opcode, arg = REVERSE_MAP[target.opcode]

            target.change_opcode(opcode)
            target.arg = arg

