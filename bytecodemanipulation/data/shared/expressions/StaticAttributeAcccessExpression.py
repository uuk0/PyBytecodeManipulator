import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor, StaticIdentifier


class StaticAttributeAccessExpression(AbstractAccessExpression):
    IS_STATIC = True

    def __init__(
        self, root: AbstractAccessExpression, name: typing.Union["IIdentifierAccessor", str],
    ):
        self.root = root
        self.name = (
            name
            if not isinstance(name, str)
            else StaticIdentifier(name)
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.root == other.root
            and self.name == other.name
        )

    def __repr__(self):
        return f"{self.root}.!{self.name(None)}"

    def copy(self) -> "StaticAttributeAccessExpression":
        return StaticAttributeAccessExpression(self.root.copy(), self.name)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, scope) + [
            Instruction.create_with_token(
                self.name(scope),
                function,
                -1,
                "STATIC_ATTRIBUTE_ACCESS",
                self.name(scope),
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

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
