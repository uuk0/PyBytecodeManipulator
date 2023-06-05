import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class DerefAccessExpression(AbstractAccessExpression):
    PREFIX = "§"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.token, Opcodes.LOAD_DEREF, value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.token, Opcodes.STORE_DEREF, value
            )
        ]

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        raise NotImplementedError  # todo: implement in some cases

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
