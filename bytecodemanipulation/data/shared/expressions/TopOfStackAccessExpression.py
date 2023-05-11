import typing

from bytecodemanipulation.Opcodes import Opcodes

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import Instruction
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
                Instruction(function, -1, Opcodes.ROT_N, arg=self.offset)
                for _ in range(self.offset - 1)
            ] + [
                Instruction(function, -1, Opcodes.DUP_TOP),
                Instruction(function, -1, Opcodes.ROT_TWO),
                Instruction(function, -1, Opcodes.ROT_N, arg=self.offset),
            ]

        return []

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.offset != 0:
            raise NotImplementedError("%<n> as store target")

        return []
