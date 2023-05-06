import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class LocalAccessExpression(AbstractAccessExpression):
    PREFIX = "$"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.token, function, -1, "LOAD_FAST", value, _decode_next=False
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(self.token, function, -1, "STORE_FAST", value)
        ]
