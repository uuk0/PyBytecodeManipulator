import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import AbstractAssemblyInstruction
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.assembler.util.tokenizer import IntegerToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class StoreFastAssembly(AbstractAssemblyInstruction):
    # STORE_FAST <name> [<source>]
    NAME = "STORE_FAST"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "StoreFastAssembly":
        parser.try_consume(SpecialToken("$"))
        name = parser.consume([IdentifierToken, IntegerToken])

        source = parser.try_parse_data_source()

        return cls(name, source)

    def __init__(
        self,
        name_token: IdentifierToken | IntegerToken | str | int,
        source: AbstractSourceExpression | None = None,
    ):
        self.name_token = (
            name_token
            if not isinstance(name_token, (str, int))
            else (
                IdentifierToken(name_token)
                if isinstance(name_token, str)
                else IntegerToken(str(name_token))
            )
        )
        self.source = source

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name_token == other.name_token
            and self.source == other.source
        )

    def __repr__(self):
        return f"STORE_FAST({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "StoreFastAssembly":
        return StoreFastAssembly(self.name, self.source.copy() if self.source else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + [Instruction(function, -1, "STORE_FAST", value)]

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.source.visit_parts(visitor) if self.target else None,)
        )
