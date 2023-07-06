import builtins
import os
import sys
import types
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


root = __file__
for _ in range(5):
    root = os.path.dirname(root)


with open(root+"/setup.py", mode="r") as f :
    line = list(f.readlines())[8].strip()

    if not line.startswith("version="):
        raise RuntimeError("could not find version information")

    parts = list(map(int, line.removeprefix("version=\"").removesuffix("\",").split(".")))
    BCM_VERSION = parts[0] * 10000 + parts[1] * 100 + parts[2]


class ModuleAccessExpression(AbstractAccessExpression):
    IS_STATIC = True
    PREFIX = "~"
    _CACHE = builtins.__dict__.copy()

    _CACHE.update({
        "PY_VERSION": sys.version_info.major * 100 + sys.version_info.minor,
        "BCM_VERSION": BCM_VERSION,
    })

    @classmethod
    def _cached_lookup(cls, module_name: str) -> types.ModuleType:
        if module_name not in cls._CACHE:
            module = cls._CACHE[module_name] = __import__(module_name)
            return module

        return cls._CACHE[module_name]

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        try:
            value = self._cached_lookup(self.get_name(scope))
        except (ModuleNotFoundError, ImportError):
            raise throw_positioned_error(
                scope,
                [self.token] + list(self.name.get_tokens()),
                f"expected <module>, got '{self.name(scope)}'",
            )

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
