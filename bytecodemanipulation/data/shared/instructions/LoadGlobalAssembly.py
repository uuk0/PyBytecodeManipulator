import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
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

        # todo: make parse_identifier_like()
        name = parser.try_consume(IdentifierToken)

        if name is None:
            raise PropagatingCompilerException(
                "expected <name>"
            ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        if parser.try_consume(SpecialToken("-")):
            if not parser.try_consume(SpecialToken(">")):
                raise PropagatingCompilerException(
                    "expected '>' after '-'"
                ).add_trace_level(scope.get_trace_info().with_token(parser[-1:1], scope.last_base_token))

            target = parser.try_consume_access_to_value(scope=scope)

            if target is None:
                raise PropagatingCompilerException(
                    "expected <expression> after '->'"
                ).add_trace_level(scope.get_trace_info().with_token(parser[0]))
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
