import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.assembler.AbstractBase import (
    IIdentifierAccessor,
    StaticIdentifier,
)
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class StaticAttributeAccessExpression(AbstractAccessExpression):
    IS_STATIC = True

    def __init__(
        self,
        root: AbstractAccessExpression,
        name: typing.Union["IIdentifierAccessor", str],
    ):
        self.root = root
        self.name = name if not isinstance(name, str) else StaticIdentifier(name)

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
                tuple(self.name.get_tokens())[0],
                Opcodes.STATIC_ATTRIBUTE_ACCESS,
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

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        base = self.root.evaluate_static_value(scope)

        if not hasattr(base, self.name(scope)):
            raise NotImplementedError

        return getattr(base, self.name(scope))

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return list(self.root.get_tokens()) + [self.token]
