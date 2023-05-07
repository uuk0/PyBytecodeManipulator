import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractReturnAssembly(AbstractAssemblyInstruction, abc.ABC):
    # # RETURN [<expr>]
    NAME = "RETURN"

    def __init__(self, expr: AbstractSourceExpression | None = None):
        self.expr = expr

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractReturnAssembly":
        return cls(
            parser.try_parse_data_source(
                allow_primitives=True, allow_op=True, include_bracket=False, scope=scope
            )
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
            (self.expr.visit_parts(visitor, parents + [self]) if self.expr else None,),
            parents,
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.expr == other.expr

    def __repr__(self):
        return f"RETURN({self.expr})"

    def copy(self) -> "AbstractReturnAssembly":
        return type(self)(self.expr.copy())
