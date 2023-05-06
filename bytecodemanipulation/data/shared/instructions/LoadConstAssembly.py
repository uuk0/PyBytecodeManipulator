import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import (
    ConstantAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.GlobalAccessExpression import (
    GlobalAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractLoadConstAssembly(AbstractAssemblyInstruction, abc.ABC):
    # LOAD_CONST <expression> | @<global const source> [-> <target>]
    NAME = "LOAD_CONST"

    def __init__(
        self,
        value: ConstantAccessExpression | GlobalAccessExpression | typing.Any,
        target: AbstractAccessExpression | None = None,
    ):
        self.value = (
            value
            if isinstance(value, (ConstantAccessExpression, GlobalAccessExpression))
            else ConstantAccessExpression(value)
        )
        self.target = target

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractLoadConstAssembly":
        value = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False
        )

        if not isinstance(value, (ConstantAccessExpression, GlobalAccessExpression)):
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <constant epxression>"
            )

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(value, target)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.value == other.value
            and self.target == other.target
        )

    def __repr__(self):
        return f"LOAD_CONST({self.value.value if not isinstance(self.value, GlobalAccessExpression) else self.target}{', ' + repr(self.target) if self.target else ''})"

    def copy(self) -> "AbstractLoadConstAssembly":
        return type(self)(self.value, self.target)

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
                self.value.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target else None,
            ),
        )
