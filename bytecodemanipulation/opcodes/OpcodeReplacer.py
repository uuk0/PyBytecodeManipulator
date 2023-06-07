import sys
import typing

from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import AbstractInstructionWalkerTransform
from bytecodemanipulation.opcodes.Opcodes import Opcodes

if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction
    from bytecodemanipulation.opcodes.Instruction import Instruction


from bytecodemanipulation.data_loader import load_opcode_data

load_opcode_data()


OPCODE_DATA: typing.List[typing.Tuple[int | typing.Tuple[int, int], int | typing.Tuple[int, int]]] = [
    ((Opcodes.COMPARE_OP, 0), Opcodes.COMPARE_LT),
    ((Opcodes.COMPARE_OP, 1), Opcodes.COMPARE_LE),
    ((Opcodes.COMPARE_OP, 2), Opcodes.COMPARE_EQ),
    ((Opcodes.COMPARE_OP, 3), Opcodes.COMPARE_NEQ),
    ((Opcodes.COMPARE_OP, 4), Opcodes.COMPARE_GT),
    ((Opcodes.COMPARE_OP, 5), Opcodes.COMPARE_GE),
]


if sys.version_info[1] == 11:
    OPCODE_DATA += [
        (Opcodes.CALL, Opcodes.CALL_FUNCTION),
    ]


FORWARD_MAP = {e[0]: e[1] for e in OPCODE_DATA}
REVERSE_MAP = {e[1]: e[0] for e in OPCODE_DATA}


class RawToIntermediateOpcodeTransform(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.Any, target: "Instruction") -> typing.Any:
        if (target.opcode, target.arg) in FORWARD_MAP:
            e = FORWARD_MAP[(target.opcode, target.arg)]

            if isinstance(e, int):
                opcode = e
                arg = None
            else:
                opcode, arg = e

        elif target.opcode in FORWARD_MAP:
            e = FORWARD_MAP[target.opcode]

            if isinstance(e, int):
                opcode = e
                arg = None
            else:
                opcode, arg = e
        else:
            return

        target.change_opcode(opcode)

        if arg is not None:
            target.arg = arg


class IntermediateToRawOpcodeTransform(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.Any, target: "Instruction") -> typing.Any:
        if target.opcode in REVERSE_MAP:
            e = REVERSE_MAP[target.opcode]

            if isinstance(e, int):
                opcode = e
                arg = None
            else:
                opcode, arg = e

        elif (target.opcode, target.arg) in REVERSE_MAP:
            e = REVERSE_MAP[target.opcode, target.arg]

            if isinstance(e, int):
                opcode = e
                arg = None
            else:
                opcode, arg = e

        else:
            return

        target.change_opcode(opcode)

        if arg is not None:
            target.arg = arg


class PrecallInserterTransform(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.Any, target: "Instruction") -> typing.Any:
        if target.opcode in (Opcodes.CALL_FUNCTION, Opcodes.CALL) and not any(e.opcode == Opcodes.PRECALL for e in target.previous_instructions):
            call = target.copy()
            target.insert_after(call)
            target.change_opcode(Opcodes.PRECALL)
