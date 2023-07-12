import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException, TraceInfo
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class MacroParameterAccessExpression(AbstractAccessExpression):
    PREFIX = "&"

    def __init__(
        self,
        name: "IIdentifierAccessor | str",
        token: AbstractToken | typing.List[AbstractToken] = None,
        trace_info: TraceInfo = None,
    ):
        super().__init__(name, token)
        self.trace_info: TraceInfo = trace_info

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.get_name(scope)

        try:
            value_deref = scope.lookup_macro_parameter(value)
        except KeyError:
            raise PropagatingCompilerException(
                f"Name '{value}' not found in macro var space"
            ).add_trace_level(self.trace_info.with_token(self.token))

        if value_deref != self and hasattr(value_deref, "emit_bytecodes"):
            instructions = value_deref.emit_bytecodes(function, scope)

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

        try:
            deref_value = scope.lookup_macro_parameter(value)
        except KeyError:
            raise PropagatingCompilerException(f"Name '{value}' not found in macro var space").add_trace_level(self.trace_info) from None

        if deref_value != self and hasattr(deref_value, "emit_bytecodes"):
            instructions = deref_value.emit_store_bytecodes(function, scope)

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

        try:
            obj = scope.lookup_macro_parameter(name)
        except KeyError:
            raise NotImplementedError from None

        return obj.evaluate_static_value(scope)

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
