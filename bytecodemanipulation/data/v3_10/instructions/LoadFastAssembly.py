import typing

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.LoadFastAssembly import (
    AbstractLoadFastAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class LoadFastAssembly(AbstractLoadFastAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_FAST", value)] + (
            self.target.emit_bytecodes(function, scope) if self.target else []
        )
