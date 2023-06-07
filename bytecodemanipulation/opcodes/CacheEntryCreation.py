import dis
import sys
import typing

from bytecodemanipulation.opcodes.CodeObjectBuilder import CodeObjectBuilder
from bytecodemanipulation.opcodes.Opcodes import Opcodes
from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import AbstractInstructionWalkerTransform

if typing.TYPE_CHECKING:
    from bytecodemanipulation.opcodes.Instruction import Instruction
    from bytecodemanipulation.MutableFunction import MutableFunction


CACHE_COUNT: typing.Dict[int, int] = {}


if sys.version_info[1] >= 11:
    for opname, info in dis._cache_format.items():
        CACHE_COUNT[getattr(Opcodes, opname)] = info["counter"]

    CACHE_COUNT.update({
        Opcodes.PRECALL: 1,
        Opcodes.CALL: 4,
    })


class CacheInstructionCreator(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", builder: CodeObjectBuilder, target: "Instruction") -> typing.Any:
        if target.opcode in CACHE_COUNT:
            from bytecodemanipulation.opcodes.Instruction import Instruction

            # target.insert_after([
            #     Instruction(Opcodes.CACHE)
            #     for _ in range(CACHE_COUNT[target.opcode])
            # ])


