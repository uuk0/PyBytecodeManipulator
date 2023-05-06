import typing

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.YieldAssembly import (
    AbstractYieldAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


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
                Instruction(function, -1, Opcodes.GET_YIELD_FROM_ITER),
                Instruction(function, -1, Opcodes.LOAD_CONST, None),
                Instruction(function, -1, Opcodes.YIELD_FROM),
            ]

        else:
            bytecode += [
                Instruction(function, -1, Opcodes.YIELD_VALUE),
            ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)

        else:
            bytecode += [Instruction(function, -1, Opcodes.POP_TOP)]

        # print(bytecode)

        return bytecode
