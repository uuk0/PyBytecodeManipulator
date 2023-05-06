import builtins
import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class GlobalStaticAccessExpression(AbstractAccessExpression):
    PREFIX = "@!"
    IS_STATIC = True

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        key = self.get_name(scope)
        global_dict = function.target.__globals__
        if key not in global_dict and hasattr(builtins, key):
            value = getattr(builtins, key)
        else:
            value = global_dict.get(key)

        return [
            Instruction.create_with_token(self.name, function, -1, "LOAD_CONST", value)
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError("Cannot assign to a constant global")

    def get_static_value(self, scope: ParsingScope) -> typing.Any:
        if self.get_name(scope) in scope.globals_dict:
            return scope.globals_dict[self.get_name(scope)]

        raise throw_positioned_syntax_error(
            scope,
            self.token,
            f"Name {self.get_name(scope)} not found!",
            NameError,
        )
