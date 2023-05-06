import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class StoreAssembly(AbstractAssemblyInstruction):
    # STORE <access> [(expression)]
    NAME = "STORE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "StoreAssembly":
        access = parser.try_consume_access_to_value(
            allow_tos=False, scope=scope, allow_calls=False
        )

        if access is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        source = parser.try_parse_data_source()

        return cls(access, source)

    def __init__(
        self,
        access_token: AbstractAccessExpression,
        source: AbstractSourceExpression | None = None,
    ):
        self.access_token = access_token
        self.source = source

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.access_token == other.access_token
            and self.source == other.source
        )

    def __repr__(self):
        return f"STORE({self.access_token}, {self.source})"

    def copy(self) -> "StoreAssembly":
        return StoreAssembly(
            self.access_token, self.source.copy() if self.source else None
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + self.access_token.emit_store_bytecodes(function, scope)

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self,
            (
                self.access_token.visit_parts(visitor, parents + [self]),
                self.source.visit_parts(visitor, parents + [self])
                if self.source is not None
                else None,
            ),
            parents,
        )
