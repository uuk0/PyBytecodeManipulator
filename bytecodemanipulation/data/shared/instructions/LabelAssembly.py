import typing

from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.AbstractBase import StaticIdentifier
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class LabelAssembly(AbstractAssemblyInstruction):
    # LABEL <name>
    NAME = "LABEL"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "LabelAssembly":
        name = parser.try_parse_identifier_like()

        if name is None:
            raise throw_positioned_syntax_error(
                scope, parser[0], "expected <identifier like>"
            )

        return cls(name)

    def __init__(self, name: IIdentifierAccessor | str):
        self.name = name if not isinstance(name, str) else StaticIdentifier(name)

    def __repr__(self):
        return f"LABEL({self.name})"

    def __eq__(self, other):
        return type(self) == type(other) and self.name == other.name

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction(function, -1, Opcodes.BYTECODE_LABEL, self.name(scope))]

    def copy(self) -> "LabelAssembly":
        return type(self)(self.name)

    def get_labels(self, scope: ParsingScope) -> typing.Set[StaticIdentifier]:
        return {StaticIdentifier(self.name(scope))}
