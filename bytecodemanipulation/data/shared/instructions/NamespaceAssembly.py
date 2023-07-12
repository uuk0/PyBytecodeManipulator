import typing

from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException, TraceInfo
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
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

        try:
            assembly = parser.parse_body(namespace_part=[e.text for e in name], scope=scope)
        except PropagatingCompilerException as e:
            e.add_trace_level(scope.get_trace_info().with_token(name), f"during parsing namespace body of {':'.join(map(lambda e: e.text, name))}")
            raise e

        return cls(
            name,
            assembly,
            trace_info=scope.get_trace_info().with_token(name),
        )

    def __init__(
        self, name: typing.List[IdentifierToken], assembly: CompoundExpression, trace_info: TraceInfo = None
    ):
        self.name = name
        self.assembly = assembly
        self.trace_info = trace_info

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
        try:
            return self.assembly.emit_bytecodes(
                function, scope.copy(sub_scope_name=[e.text for e in self.name])
            )
        except PropagatingCompilerException as e:
            e.add_trace_level(self.trace_info, f"during emitting namespace body of {':'.join(map(lambda e: e.text, self.name))}")
            raise e

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
