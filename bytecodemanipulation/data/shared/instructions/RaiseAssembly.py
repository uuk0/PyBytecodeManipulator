import abc

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractRaiseAssembly(AbstractAssemblyInstruction, abc.ABC):
    # RAISE [<source>]
    NAME = "RAISE"

    def __init__(self, source):
        self.source = source

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "AbstractRaiseAssembly":
        return cls(parser.try_parse_data_source(include_bracket=False))

    def __eq__(self, other):
        return type(self) == type(other) and self.source == other.source

    def __repr__(self):
        return f"RAISE({'TOS' if self.source is None else self.source})"

    def copy(self):
        return type(self)(self.source.copy() if self.source else None)
