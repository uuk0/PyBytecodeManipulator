import typing

from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class MacroReturnAssembly(AbstractAssemblyInstruction):
    NAME = "MACRO_RETURN"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "MacroReturnAssembly":
        return cls(
            parser.try_parse_data_source(
                allow_primitives=True, allow_op=True, include_bracket=False
            )
        )

    def __init__(self, expr: AbstractSourceExpression | None = None):
        self.expr = expr

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
            (self.expr.visit_parts(visitor, parents + [self]) if self.expr else None,),
            parents,
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.expr == other.expr

    def __repr__(self):
        return f"MACRO_RETURN({self.expr})"

    def copy(self) -> "MacroReturnAssembly":
        return MacroReturnAssembly(self.expr.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        expr_bytecode = self.expr.emit_bytecodes(function, scope) if self.expr else []

        return expr_bytecode + [Instruction(function, -1, Opcodes.MACRO_RETURN_VALUE)]
