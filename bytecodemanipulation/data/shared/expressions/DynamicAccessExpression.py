import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class DynamicAttributeAccessExpression(AbstractAccessExpression):
    def __init__(
        self, root: AbstractAccessExpression, name_expr: AbstractSourceExpression
    ):
        self.root = root
        self.name_expr = name_expr

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.root == other.root
            and self.name_expr == other.name_expr
        )

    def __repr__(self):
        return f"{self.root}.{self.name_expr}"

    def copy(self) -> "DynamicAttributeAccessExpression":
        return DynamicAttributeAccessExpression(self.root.copy(), self.name_expr.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [Instruction(Opcodes.LOAD_CONST, getattr)]
            + self.root.emit_bytecodes(function, scope)
            + self.name_expr.emit_bytecodes(function, scope)
            + [Instruction(Opcodes.CALL_FUNCTION, arg=2)]
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [Instruction(Opcodes.LOAD_CONST, setattr)]
            + self.root.emit_bytecodes(function, scope)
            + self.name_expr.emit_bytecodes(function, scope)
            + [
                Instruction(Opcodes.ROT_THREE),
                Instruction(Opcodes.CALL_FUNCTION, arg=2),
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
            self, (self.root.visit_parts(visitor, parents + [self]),), parents
        )

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        base = self.root.evaluate_static_value(scope)
        name = self.name_expr.evaluate_static_value(scope)

        if not hasattr(base, name):
            raise NotImplementedError

        return getattr(base, name)

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return list(self.root.get_tokens()) + list(self.name_expr.get_tokens())
