import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class CompoundExpression(AbstractExpression, IAssemblyStructureVisitable):
    def __init__(self, children: typing.List[AbstractExpression] = None):
        self.children = children or []

    def __eq__(self, other):
        return type(self) == type(other) and self.children == other.children

    def __repr__(self):
        return f"Compound({repr(self.children)[1:-1]})"

    def copy(self) -> "CompoundExpression":
        return CompoundExpression([child.copy() for child in self.children])

    def add_child(self, expr: "AbstractExpression"):
        self.children.append(expr)
        return self

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return sum(
            (child.emit_bytecodes(function, scope) for child in self.children), []
        )

    def fill_scope_complete(self, scope: ParsingScope):
        def visitor(
            expression: AbstractExpression,
            _,
            parents: typing.List[AbstractAccessExpression],
        ):
            from bytecodemanipulation.data.shared.instructions.NamespaceAssembly import (
                NamespaceAssembly,
            )

            if (
                hasattr(expression, "fill_scope")
                and type(expression).fill_scope
                != AbstractAssemblyInstruction.fill_scope
            ):
                scope.scope_path = sum(
                    [
                        [expr.name.text]
                        for expr in parents
                        if isinstance(expr, NamespaceAssembly)
                    ],
                    [],
                )
                expression.fill_scope(scope)

        self.visit_parts(visitor, [])
        return scope

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
            tuple(
                [
                    child.visit_parts(visitor, parents + [self])
                    for child in self.children
                ]
            ),
            parents,
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            tuple(
                [child.visit_assembly_instructions(visitor) for child in self.children]
            ),
        )

    def collect_label_info(self, scope: ParsingScope) -> typing.Set[str]:
        return self.get_labels(scope)

    def get_labels(self, scope: ParsingScope) -> typing.Set[str]:
        result = set()

        for instr in self.children:
            result.update(instr.get_labels(scope))

        return result

    def create_bytecode(self, target: MutableFunction, scope: ParsingScope):
        return self.emit_bytecodes(target, scope)
