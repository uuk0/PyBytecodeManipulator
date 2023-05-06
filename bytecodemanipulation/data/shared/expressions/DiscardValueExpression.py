import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


class DiscardValueExpression(AbstractAccessExpression):
    def __init__(self, token=None):
        self.token = token

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction(function, -1, Opcodes.POP_TOP)]
