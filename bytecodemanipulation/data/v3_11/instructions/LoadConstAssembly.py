import typing

from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import (
    ConstantAccessExpression,
)
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.LoadConstAssembly import (
    AbstractLoadConstAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class LoadConstAssembly(AbstractLoadConstAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [
            Instruction(
                function,
                -1,
                "LOAD_CONST",
                self.value.value
                if isinstance(self.value, ConstantAccessExpression)
                else function.target.__globals__.get(self.value.name_token.text),
            )
        ] + (self.target.emit_bytecodes(function, scope) if self.target else [])
