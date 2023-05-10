import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken, IntegerToken
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction


@Parser.register
class RawAssembly(AbstractAssemblyInstruction):
    # RAW <opcode_or_name> [<arg>]
    NAME = "RAW"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "RawAssembly":
        return cls(
            parser.consume([IdentifierToken, IntegerToken]),
            parser.try_consume(IntegerToken),
        )

    def __init__(
        self, opcode_or_name: IdentifierToken | IntegerToken, arg: IntegerToken = None
    ):
        self.opcode_or_name = opcode_or_name
        self.arg = arg

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.opcode_or_name == other.opcode_or_name
            and self.arg == other.arg
        )

    def __repr__(self):
        return f"RAW({self.opcode_or_name.text}, {self.arg.text if self.arg else None})"

    def copy(self):
        return type(self)(self.opcode_or_name, self.arg)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        opcode = self.opcode_or_name.text

        if opcode.isdigit():
            opcode = int(opcode)

        return [
            Instruction.create_with_token(
                self.opcode_or_name,
                function,
                -1,
                opcode,
                arg=0 if self.arg is None else int(self.arg.text),
            ),
        ]
