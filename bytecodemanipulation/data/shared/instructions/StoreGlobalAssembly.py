import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.assembler.util.tokenizer import IntegerToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractStoreGlobalAssembly(AbstractAssemblyInstruction, abc.ABC):
    # STORE_GLOBAL <name> [<source>]
    NAME = "STORE_GLOBAL"

    def __init__(
        self,
        name_token: IdentifierToken | IntegerToken | str | int,
        source: AbstractSourceExpression | None = None,
    ):
        self.name_token = (
            (
                IdentifierToken(name_token)
                if isinstance(name_token, str)
                else IntegerToken(str(name_token))
            )
            if isinstance(name_token, (str, int))
            else name_token
        )
        self.source = source

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractStoreGlobalAssembly":
        parser.try_consume(SpecialToken("@"))

        # todo: make parse_identifier_like()
        name = parser.try_consume(IdentifierToken)

        if name is None:
            raise PropagatingCompilerException("expected <name>").add_trace_level(
                scope.get_trace_info().with_token(parser[0])
            )

        source = parser.try_consume_access_to_value_with_brackets(scope=scope)

        return cls(name, source)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name_token == other.name_token
            and self.source == other.source
        )

    def __repr__(self):
        return f"STORE_GLOBAL({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "AbstractStoreGlobalAssembly":
        return type(self)(self.name_token, self.source.copy() if self.source else None)

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.source.visit_parts(visitor, []) if self.source else None,)
        )
