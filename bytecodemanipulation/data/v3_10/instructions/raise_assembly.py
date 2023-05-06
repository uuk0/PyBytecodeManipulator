import typing

from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class RaiseAssembly(AbstractAssemblyInstruction):
    # RAISE [<source>]
    NAME = "RAISE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "RaiseAssembly":
        return cls(parser.try_parse_data_source(include_bracket=False))

    def __init__(self, source: AbstractSourceExpression = None):
        self.source = source

    def __eq__(self, other):
        return type(self) == type(other) and self.source == other.source

    def __repr__(self):
        return f"RAISE({'TOS' if self.source is None else self.source})"

    def copy(self):
        return type(self)(self.source.copy() if self.source else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + [Instruction(function, -1, Opcodes.RAISE_VARARGS, arg=1)]
