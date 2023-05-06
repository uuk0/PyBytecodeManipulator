import typing

from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


class NamespaceAssembly(AbstractAssemblyInstruction):
    # 'NAMESPACE' [{<namespace> ':'}] <name> '{' <code> '}'
    NAME = "NAMESPACE"

    @classmethod
    def register(cls):
        from bytecodemanipulation.assembler.Parser import Parser

        Parser.register(cls)

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "NamespaceAssembly":
        name = [parser.consume(IdentifierToken)]

        while parser.try_consume(SpecialToken(":")):
            name.append(parser.consume(IdentifierToken))

        assembly = parser.parse_body(namespace_part=[e.text for e in name], scope=scope)

        return cls(
            name,
            assembly,
        )

    def __init__(
        self, name: typing.List[IdentifierToken], assembly: CompoundExpression
    ):
        self.name = name
        self.assembly = assembly

    def __repr__(self):
        return (
            f"NAMESPACE::'{':'.join(e.text for e in self.name)}'({repr(self.assembly)})"
        )

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.name == other.name
            and self.assembly == other.assembly
        )

    def copy(self):
        return type(self)(self.name, self.assembly.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.assembly.emit_bytecodes(
            function, scope.copy(sub_scope_name=[e.text for e in self.name])
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
                self.assembly.visit_parts(
                    visitor,
                    parents + [self],
                ),
            ),
            parents,
        )
