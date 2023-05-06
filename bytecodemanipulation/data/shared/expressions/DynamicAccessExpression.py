import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


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
            [Instruction(function, -1, Opcodes.LOAD_CONST, getattr)]
            + self.root.emit_bytecodes(function, scope)
            + self.name_expr.emit_bytecodes(function, scope)
            + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)]
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [Instruction(function, -1, Opcodes.LOAD_CONST, setattr)]
            + self.root.emit_bytecodes(function, scope)
            + self.name_expr.emit_bytecodes(function, scope)
            + [
                Instruction(function, -1, Opcodes.ROT_THREE),
                Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2),
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
