import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.instructions.OpAssembly import AbstractOpAssembly


class AbstractJumpAssembly(AbstractAssemblyInstruction, abc.ABC):
    NAME = "JUMP"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractJumpAssembly":
        has_quotes = parser.try_consume(SpecialToken("'"))

        label_target = parser.consume(IdentifierToken)

        if has_quotes:
            parser.consume(SpecialToken("'"))

        if parser.try_consume(IdentifierToken("IF")):
            condition = parser.try_parse_data_source(
                allow_primitives=True, include_bracket=False, allow_op=True
            )

        elif parser.try_consume(SpecialToken("(")):
            parser.save()
            condition = parser.try_parse_data_source(
                allow_primitives=True, include_bracket=False, allow_op=True
            )

            if condition is None or not parser.try_consume(SpecialToken(")")):
                parser.rollback()
                condition = AbstractOpAssembly.IMPLEMENTATION.consume(parser, None)
                parser.consume(SpecialToken(")"))
            else:
                parser.discard_save()

        else:
            condition = None

        return cls(label_target, condition)

    def __init__(
        self,
        label_name_token: IdentifierToken | str,
        condition: AbstractAccessExpression | None = None,
    ):
        self.label_name_token = (
            label_name_token
            if isinstance(label_name_token, IdentifierToken)
            else IdentifierToken(label_name_token)
        )
        self.condition = condition

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
                self.condition.visit_parts(visitor, parents + [self])
                if self.condition
                else None,
            ),
            parents,
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.label_name_token == other.label_name_token
            and self.condition == other.condition
        )

    def __repr__(self):
        return f"JUMP({self.label_name_token.text}{'' if self.condition is None else ', IF '+repr(self.condition)})"

    def copy(self) -> "AbstractJumpAssembly":
        return type(self)(
            self.label_name_token, self.condition.copy() if self.condition else None
        )
