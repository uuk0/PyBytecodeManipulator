import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.AbstractBase import StaticIdentifier
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractWhileAssembly(AbstractAssemblyInstruction, abc.ABC):
    # # WHILE <expression> ['\'' <label name> '\''] '{' <body> '}'
    NAME = "WHILE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "AbstractWhileAssembly":
        condition = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False, scope=scope
        )

        if condition is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        if parser.try_consume(SpecialToken("'")):
            label_name = parser.parse_identifier_like(scope)
            if not parser.try_consume(SpecialToken("'")):
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected '"
                )
        else:
            label_name = None

        body = parser.parse_body(scope=scope)

        return cls(
            condition,
            body,
            label_name,
        )

    def __init__(
        self,
        source: AbstractSourceExpression,
        body: CompoundExpression,
        label_name: IIdentifierAccessor | None = None,
    ):
        self.source = source
        self.body = body
        self.label_name = (
            label_name
            if not isinstance(label_name, str)
            else StaticIdentifier(label_name)
        )

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy(), self.label_name)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.body == other.body
            and self.label_name == other.label_name
        )

    def __repr__(self):
        c = "'"
        return f"WHILE({self.source}{'' if self.label_name is None else ', label='+c+repr(self.label_name)+c}) -> {{{self.body}}}"

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.source.visit_parts(visitor), self.body.visit_parts(visitor))
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))

    def get_labels(self, scope: ParsingScope):
        return (
            set()
            if self.label_name is None
            else {
                self.label_name(scope),
                self.label_name(scope) + "_END",
                self.label_name(scope) + "_INNER",
            }
        ) | self.body.get_labels(scope)
