import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.assembler.AbstractBase import (
    IIdentifierAccessor,
    StaticIdentifier,
)


class AttributeAccessExpression(AbstractAccessExpression):
    def __init__(
        self,
        root: AbstractAccessExpression,
        name: IIdentifierAccessor | str,
        trace_info=None,
    ):
        self.root = root
        self.name = name if not isinstance(name, str) else StaticIdentifier(name)
        self.trace_info = trace_info

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.root == other.root
            and self.name == other.name
        )

    def __repr__(self):
        return f"{self.root}.{self.name(None)}"

    def copy(self) -> "AttributeAccessExpression":
        return AttributeAccessExpression(self.root.copy(), self.name)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, scope) + [
            Instruction("LOAD_ATTR", self.name(scope))
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, scope) + [
            Instruction("STORE_ATTR", self.name(scope))
        ]

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

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return list(self.root.get_tokens()) + list(self.name.get_tokens())

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        raise NotImplementedError
