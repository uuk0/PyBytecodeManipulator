import builtins
import types
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class ModuleAccessExpression(AbstractAccessExpression):
    IS_STATIC = True
    PREFIX = "~"
    _CACHE = builtins.__dict__.copy()

    @classmethod
    def _cached_lookup(cls, module_name: str) -> types.ModuleType:
        if module_name not in cls._CACHE:
            module = cls._CACHE[module_name] = __import__(module_name)
            return module

        return cls._CACHE[module_name]

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self._cached_lookup(self.get_name(scope))
        return [
            Instruction.create_with_token(
                self.token, Opcodes.LOAD_CONST, value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        return self._cached_lookup(self.get_name(scope))

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
