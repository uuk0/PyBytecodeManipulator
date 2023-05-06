import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
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


class AbstractLoadGlobalAssembly(AbstractAssemblyInstruction, abc.ABC):
    # # LOAD_GLOBAL <name> [-> <target>]
    NAME = "LOAD_GLOBAL"

    def __init__(
        self,
        name_token: IdentifierToken | IntegerToken | str | int,
        target: AbstractAccessExpression | None = None,
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
        self.target = target

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractLoadGlobalAssembly":
        parser.try_consume(SpecialToken("@"))

        name = parser.try_consume([IdentifierToken, IntegerToken])

        if name is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <name> or <integer>"
            )

        if parser.try_consume(SpecialToken("-")):
            if not parser.try_consume(SpecialToken(">")):
                raise throw_positioned_syntax_error(
                    scope,
                    parser[-1:1] + [scope.last_base_token],
                    "expected '>' after '-'",
                )

            target = parser.try_consume_access_to_value(scope=scope)

            if target is None:
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected <expression>"
                )
        else:
            target = None

        return cls(name, target)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name_token == other.name_token
            and self.target == other.target
        )

    def __repr__(self):
        return f"LOAD_GLOBAL({self.name_token}{', ' + repr(self.target) if self.target else ''})"

    def copy(self) -> "AbstractLoadGlobalAssembly":
        return type(self)(self.name_token, self.target)

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.target.visit_parts(visitor) if self.target else None,)
        )
