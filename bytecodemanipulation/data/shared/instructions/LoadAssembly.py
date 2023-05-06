import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class LoadAssembly(AbstractAssemblyInstruction):
    # LOAD <access> [-> <target>]
    NAME = "LOAD"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "LoadAssembly":
        access_expr = parser.try_consume_access_to_value(
            allow_tos=False, allow_primitives=True, scope=scope
        )

        if access_expr is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        if parser.try_consume(SpecialToken("-")):
            if not parser.try_consume(SpecialToken(">")):
                raise throw_positioned_syntax_error(
                    scope,
                    parser[-1:1] + [scope.last_base_token],
                    "expected '>' after '-' to complete '->'",
                )

            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(access_expr, target)

    def __init__(
        self,
        access_expr: AbstractAccessExpression,
        target: AbstractAccessExpression | None = None,
    ):
        self.access_expr = access_expr
        self.target = target

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.access_expr == other.access_expr
            and self.target == other.target
        )

    def __repr__(self):
        return (
            f"LOAD({self.access_expr}{', ' + repr(self.target) if self.target else ''})"
        )

    def copy(self) -> "LoadAssembly":
        return LoadAssembly(self.access_expr, self.target)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.access_expr.emit_bytecodes(function, scope) + (
            self.target.emit_store_bytecodes(function, scope) if self.target else []
        )

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
                self.access_expr.visit_parts(visitor, parents + [self]),
                self.target.visit_parts(visitor, parents + [self])
                if self.target is not None
                else None,
            ),
            parents,
        )
