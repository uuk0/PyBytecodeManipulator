import typing

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.ReturnAssembly import (
    AbstractReturnAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class ReturnAssembly(AbstractReturnAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        expr_bytecode = self.expr.emit_bytecodes(function, scope) if self.expr else []

        return expr_bytecode + [Instruction(function, -1, "RETURN_VALUE")]
