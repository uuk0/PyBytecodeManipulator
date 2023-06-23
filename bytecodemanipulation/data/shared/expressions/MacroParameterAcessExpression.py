import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class MacroParameterAccessExpression(AbstractAccessExpression):
    PREFIX = "&"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value not in scope.macro_parameter_namespace:
            raise throw_positioned_error(
                scope, self.token, "Name not found in macro var space"
            )

        if scope.macro_parameter_namespace[value] != self and hasattr(
            scope.macro_parameter_namespace[value], "emit_bytecodes"
        ):
            instructions = scope.macro_parameter_namespace[value].emit_bytecodes(
                function, scope
            )

            for instr in instructions:
                if instr.has_local():
                    instr.change_arg_value(":" + instr.arg_value)

            return instructions

        return [
            Instruction.create_with_token(
                self.token, Opcodes.MACRO_LOAD_PARAMETER, value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        if value not in scope.macro_parameter_namespace:
            raise throw_positioned_error(
                scope, self.token, "Name not found in macro var space"
            )

        if scope.macro_parameter_namespace[value] != self and hasattr(
            scope.macro_parameter_namespace[value], "emit_bytecodes"
        ):
            instructions = scope.macro_parameter_namespace[value].emit_store_bytecodes(
                function, scope
            )

            for instr in instructions:
                if instr.has_local():
                    instr.change_arg_value(":" + instr.arg_value)

            return instructions

        return [
            Instruction.create_with_token(
                self.token, Opcodes.MACRO_STORE_PARAMETER, value
            )
        ]

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        name = self.name(scope)

        if name not in scope.macro_parameter_namespace:
            raise NotImplementedError

        return scope.macro_parameter_namespace[name].evaluate_static_value(scope)

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
