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


class AbstractIFAssembly(AbstractAssemblyInstruction, abc.ABC):
    # IF <expression> ['\'' <label name> '\''] '{' <body> '}'
    NAME = "IF"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "AbstractIFAssembly":
        source = parser.try_consume_access_to_value(allow_primitives=True, scope=scope)

        if source is None:
            raise PropagatingCompilerException(
                "expected <expression> after IF"
            ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        if parser.try_consume(SpecialToken("'")):
            label_name = parser.parse_jump_target(scope)

            if not parser.try_consume(SpecialToken("'")):
                raise PropagatingCompilerException(
                    "expected ' after label name declaration"
                ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        else:
            label_name = None

        body = parser.parse_body(scope=scope)

        return cls(
            source,
            body,
            label_name,
        )

    def __init__(
        self,
        source: AbstractSourceExpression,
        body: CompoundExpression,
        label_name: typing.List[IIdentifierAccessor] | str = None,
    ):
        self.source = source
        self.body = body
        self.label_name = (
            (
                [StaticIdentifier(e) for e in label_name.split(":")]
                if isinstance(label_name, str)
                else label_name
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
        c = '"'
        return f"IF({self.source}{'' if self.label_name is None else f', label={c}' + ':'.join(map(repr, self.label_name)) + c}) -> {{{self.body}}}"

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
                self.source.visit_parts(visitor, parents + [self]),
                self.body.visit_parts(visitor, parents + [self]),
            ),
            parents,
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))

    def get_labels(self, scope: ParsingScope) -> typing.Set[str]:
        label_name = (
            ":".join(e(scope) for e in self.label_name)
            if self.label_name is not None
            else None
        )

        return (
            set()
            if self.label_name is None
            else {label_name, f"{label_name}:END", f"{label_name}:HEAD"}
        ) | self.body.get_labels(scope)
