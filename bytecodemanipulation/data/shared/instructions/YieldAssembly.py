import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractYieldAssembly(AbstractAssemblyInstruction, abc.ABC):
    # YIELD [*] [<expr>] [-> <target>]
    NAME = "YIELD"

    def __init__(
        self,
        expr: AbstractSourceExpression | None = None,
        is_star: bool = False,
        target: AbstractSourceExpression | None = None,
    ):
        self.expr = expr
        self.is_star = is_star
        self.target = target

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractYieldAssembly":
        is_star = bool(parser.try_consume(SpecialToken("*")))

        expr = parser.try_consume_access_to_value(allow_primitives=True, scope=scope)

        if parser.try_consume(SpecialToken("-")) and parser.try_consume(
            SpecialToken(">")
        ):
            target = parser.try_consume_access_to_value(
                allow_primitives=True, scope=scope
            )

            if target is None:
                raise PropagatingCompilerException(
                    "expected <expression> after '->'"
                ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        else:
            target = None

        return cls(expr, is_star, target)

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
                self.expr.visit_parts(visitor, parents + [self]) if self.expr else None,
                self.target.visit_parts(
                    visitor,
                    parents + [self],
                )
                if self.target
                else None,
            ),
            parents,
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.expr == other.expr
            and self.is_star == other.is_star
            and self.target == other.target
        )

    def __repr__(self):
        return f"YIELD{'' if not self.is_star else '*'}({self.expr if self.expr else ''}{(', ' if self.expr else '->') + repr(self.target) if self.target else ''})"

    def copy(self) -> "AbstractYieldAssembly":
        return type(self)(
            self.expr.copy() if self.expr else None,
            self.is_star,
            self.target.copy() if self.target else None,
        )
