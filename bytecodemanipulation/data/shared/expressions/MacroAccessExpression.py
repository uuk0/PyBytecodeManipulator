import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class MacroAccessExpression(AbstractAccessExpression):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def __init__(self, name: typing.List[IdentifierToken]):
        self.name = name

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __repr__(self):
        return f"MACRO-LINK({':'.join(map(lambda e: e.text, self.name))})"

    def copy(self) -> "MacroAccessExpression":
        return type(self)(self.name.copy())

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        raise NotImplementedError  # todo: implement in some cases

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return self.name
