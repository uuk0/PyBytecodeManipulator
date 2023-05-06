import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


class MacroParameterAccessExpression(AbstractAccessExpression):
    PREFIX = "&"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value not in scope.macro_parameter_namespace:
            raise throw_positioned_syntax_error(
                scope, self.token, "Name not found in macro var space"
            )

        if scope.macro_parameter_namespace[value] != self and hasattr(
            scope.macro_parameter_namespace[value], "emit_bytecodes"
        ):
            return scope.macro_parameter_namespace[value].emit_bytecodes(
                function, scope
            )

        return [
            Instruction.create_with_token(
                self.token, function, -1, Opcodes.MACRO_LOAD_PARAMETER, value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value not in scope.macro_parameter_namespace:
            raise throw_positioned_syntax_error(
                scope, self.token, "Name not found in macro var space"
            )

        if scope.macro_parameter_namespace[value] != self and hasattr(
            scope.macro_parameter_namespace[value], "emit_bytecodes"
        ):
            return scope.macro_parameter_namespace[value].emit_store_bytecodes(
                function, scope
            )

        return [
            Instruction.create_with_token(
                self.token, function, -1, Opcodes.MACRO_STORE_PARAMETER, value
            )
        ]
