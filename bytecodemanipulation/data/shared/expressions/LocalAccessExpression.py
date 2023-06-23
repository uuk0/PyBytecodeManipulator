import typing
import warnings

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class LocalAccessExpression(AbstractAccessExpression):
    PREFIX = "$"

    def __init__(
        self,
        name: "IIdentifierAccessor | str",
        token: AbstractToken | typing.List[AbstractToken] = None,
        prefix="",
    ):
        super(LocalAccessExpression, self).__init__(name, token)
        self.prefix = prefix

    def __repr__(self):
        return f"{self.PREFIX}{self.prefix}{self.name}"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value not in scope.filled_locals:
            # todo: why is it warning for some stream tests?
            warnings.warn(SyntaxWarning(f"Expected local variable '{value}' to be set ahead of time, but might be not set (cannot infer for custom jumps)"), stacklevel=1)

        return [
            Instruction.create_with_token(
                self.token, Opcodes.LOAD_FAST, self.prefix + value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        scope.filled_locals.add(value)
        scope.filled_locals.add(self.prefix + value)

        return [
            Instruction.create_with_token(self.token, Opcodes.STORE_FAST, self.prefix + value)
        ]

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        raise NotImplementedError  # todo: implement in some cases

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
