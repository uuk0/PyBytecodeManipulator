import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
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
            name_token
            if not isinstance(name_token, (str, int))
            else (
                IdentifierToken(name_token)
                if isinstance(name_token, str)
                else IntegerToken(str(name_token))
            )
        )
        self.source = source

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractStoreGlobalAssembly":
        parser.try_consume(SpecialToken("@"))
        name = parser.try_consume([IdentifierToken, IntegerToken])

        if name is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <name> or <integer>"
            )

        source = parser.try_parse_data_source()

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
