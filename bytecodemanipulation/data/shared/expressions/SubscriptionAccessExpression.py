import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IntegerToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


class SubscriptionAccessExpression(AbstractAccessExpression):
    def __init__(
        self,
        base_expr: "AbstractAccessExpression",
        index_expr: AbstractAccessExpression | IntegerToken,
        token=None,
    ):
        self.base_expr = base_expr
        self.index_expr = index_expr
        self.token = token

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.base_expr == other.base_expr
            and self.index_expr == self.index_expr
        )

    def __repr__(self):
        return f"{self.base_expr}[{self.index_expr}]"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.base_expr.copy(), self.index_expr.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            self.base_expr.emit_bytecodes(function, scope)
            + (
                self.index_expr.emit_bytecodes(function, scope)
                if isinstance(self.index_expr, AbstractAccessExpression)
                else [
                    Instruction.create_with_token(
                        self.index_expr,
                        function,
                        -1,
                        "LOAD_CONST",
                        int(self.index_expr.text),
                    )
                ]
            )
            + [Instruction(function, -1, Opcodes.BINARY_SUBSCR)]
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            self.base_expr.emit_bytecodes(function, scope)
            + (
                self.index_expr.emit_bytecodes(function, scope)
                if isinstance(self.index_expr, AbstractAccessExpression)
                else [
                    Instruction.create_with_token(
                        self.index_expr,
                        function,
                        -1,
                        "LOAD_CONST",
                        int(self.index_expr.text),
                    )
                ]
            )
            + [
                Instruction.create_with_token(
                    self.name_token, function, -1, Opcodes.STORE_SUBSCR
                )
            ]
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
            (self.base_expr.visit_parts(visitor), self.index_expr.visit_parts(visitor)),
        )
