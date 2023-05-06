import typing

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.StoreGlobalAssembly import (
    AbstractStoreGlobalAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class StoreGlobalAssembly(AbstractStoreGlobalAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + [Instruction(function, -1, "STORE_GLOBAL", value)]
