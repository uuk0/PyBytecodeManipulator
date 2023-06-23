import copy
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class ConstantAccessExpression(AbstractAccessExpression):
    IS_STATIC = True

    def __init__(self, value, token: AbstractToken = None):
        self.value = value
        self.token = token

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.value == other.value

    def __repr__(self):
        return f"CONSTANT({repr(self.value)})"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(copy.deepcopy(self.value))

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction("LOAD_CONST", self.value)]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise throw_positioned_error(
            scope, self.token, f"Cannot assign to a constant: {self}"
        )

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        return self.value
