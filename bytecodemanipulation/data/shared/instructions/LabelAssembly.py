import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class LabelAssembly(AbstractAssemblyInstruction):
    # LABEL <name>
    NAME = "LABEL"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "LabelAssembly":
        return cls(parser.consume(IdentifierToken))

    def __init__(self, name_token: IdentifierToken | str):
        self.name_token = (
            name_token
            if isinstance(name_token, IdentifierToken)
            else IdentifierToken(name_token)
        )

    def __repr__(self):
        return f"LABEL({self.name_token.text})"

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction(function, -1, Opcodes.BYTECODE_LABEL, self.name_token.text)]

    def copy(self) -> "LabelAssembly":
        return type(self)(self.name_token)

    def get_labels(self) -> typing.Set[str]:
        return {self.name_token.text}
