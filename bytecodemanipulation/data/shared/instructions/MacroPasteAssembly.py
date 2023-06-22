import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class MacroPasteAssembly(AbstractAssemblyInstruction):
    # MACRO_PASTE <macro param name> ['->' <target>]
    NAME = "MACRO_PASTE"

    @classmethod
    def register(cls):
        Parser.register(cls)

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "MacroPasteAssembly":
        # Parse an optional § infront of the name
        parser.try_consume(SpecialToken("&"))

        name = parser.consume(IdentifierToken)

        if parser.try_consume_multi([SpecialToken("-"), SpecialToken(">")]):
            target = parser.try_consume_access_to_value(
                allow_primitives=False, scope=scope
            )
        else:
            target = None

        return cls(name, target)

    def __init__(self, name: IdentifierToken, target: AbstractAccessExpression = None):
        self.name = name
        self.target = target

    def __repr__(self):
        return f"MACRO_PASTE({self.name.text}{'' if self.target is None else '-> '+repr(self.target)})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name == other.name
            and self.target == other.target
        )

    def copy(self) -> "MacroPasteAssembly":
        return type(self)(self.name, self.target.copy() if self.target else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.name.text in scope.macro_parameter_namespace and hasattr(
            scope.macro_parameter_namespace[self.name.text], "emit_bytecodes"
        ):
            instructions = scope.macro_parameter_namespace[self.name.text].emit_bytecodes(
                function, scope
            )

            for instr in instructions:
                if instr.has_local():
                    if instr.arg_value.startswith("|"):
                        instr.change_arg_value(instr.arg_value[1:])
                    else:
                        instr.change_arg_value(":" + instr.arg_value)

            return instructions + (
                []
                if self.target is None
                else self.target.emit_store_bytecodes(function, scope)
            )

        return [
            Instruction(Opcodes.MACRO_PARAMETER_EXPANSION, self.name.text)
        ] + (
            []
            if self.target is None
            else self.target.emit_store_bytecodes(function, scope)
        )
