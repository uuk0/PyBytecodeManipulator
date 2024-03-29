import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.AbstractBase import StaticIdentifier
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.assembler.util.parser import AbstractExpression
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
        condition = parser.try_consume_access_to_value(
            allow_primitives=True, scope=scope
        )

        if condition is None:
            raise PropagatingCompilerException(
                "expected <expression> after WHILE for condition"
            ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        if parser.try_consume(SpecialToken("'")):
            label_name = parser.parse_jump_target(scope)

            if not parser.try_consume(SpecialToken("'")):
                raise PropagatingCompilerException(
                    "expected ' closing <label name>"
                ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

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
        label_name: typing.List[IIdentifierAccessor] | str | None = None,
    ):
        self.source = source
        self.body = body
        self.label_name = (
            (
                label_name
                if not isinstance(label_name, str)
                else [StaticIdentifier(e) for e in label_name.split(":")]
            )
            if label_name is not None
            else None
        )

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy(), self.label_name.copy())

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
        name = ":".join(e(scope) for e in self.label_name)

        return (
            set()
            if self.label_name is None
            else {
                name,
                name + ":END",
                name + ":INNER",
            }
        ) | self.body.get_labels(scope)
