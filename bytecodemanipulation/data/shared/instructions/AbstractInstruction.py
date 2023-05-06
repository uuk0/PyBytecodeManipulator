import typing
from abc import ABC

from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


class AbstractAssemblyInstruction(AbstractExpression, IAssemblyStructureVisitable, ABC):
    NAME: str | None = None

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractAssemblyInstruction":
        raise NotImplementedError

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise NotImplementedError

    def fill_scope_complete(self, scope: ParsingScope):
        self.visit_parts(
            lambda e, _: e.fill_scope(scope) if hasattr(e, "fill_scope") else None
        )
        return scope

    def fill_scope(self, scope: ParsingScope):
        pass

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(self, tuple(), parents)

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, tuple())

    def get_labels(self) -> typing.Set[str]:
        return set()
