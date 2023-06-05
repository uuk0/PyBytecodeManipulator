import typing

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.YieldAssembly import (
    AbstractYieldAssembly,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class YieldAssembly(AbstractYieldAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        bytecode = []

        if self.expr:
            bytecode += self.expr.emit_bytecodes(function, scope)

        if self.is_star:
            bytecode += [
                Instruction(Opcodes.GET_YIELD_FROM_ITER),
                Instruction(Opcodes.LOAD_CONST, None),
                Instruction(Opcodes.YIELD_FROM),
            ]

        else:
            bytecode += [
                Instruction(Opcodes.YIELD_VALUE),
            ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)

        else:
            bytecode += [Instruction(Opcodes.POP_TOP)]

        # print(bytecode)

        return bytecode
