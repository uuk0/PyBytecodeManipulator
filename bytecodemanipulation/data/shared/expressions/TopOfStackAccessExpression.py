import typing

from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Opcodes import Opcodes

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class TopOfStackAccessExpression(AbstractAccessExpression):
    PREFIX = "%"

    def __init__(self, token=None, offset=0):
        self.token = token
        self.offset = offset

    def __eq__(self, other):
        return type(self) == type(other)

    def __repr__(self):
        return f"%"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.token)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.offset != 0:
            return [
                Instruction(Opcodes.ROT_N, arg=self.offset)
                for _ in range(self.offset - 1)
            ] + [
                Instruction(Opcodes.DUP_TOP),
                Instruction(Opcodes.ROT_TWO),
                Instruction(Opcodes.ROT_N, arg=self.offset),
            ]

        return []

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.offset != 0:
            raise NotImplementedError("%<n> as store target")

        return []

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
