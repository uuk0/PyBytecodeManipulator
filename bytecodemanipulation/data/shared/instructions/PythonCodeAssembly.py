import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import PythonCodeToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class PythonCodeAssembly(AbstractAssemblyInstruction):
    # PYTHON '{' <code> '}'
    NAME = "PYTHON"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "PythonCodeAssembly":
        return cls(parser.consume(PythonCodeToken))

    def __init__(self, code: PythonCodeToken | str):
        self.code = code if isinstance(code, PythonCodeToken) else PythonCodeToken(code)

    def __repr__(self):
        return f"PYTHON({repr(self.code)})"

    def __eq__(self, other):
        return type(self) == type(other) and self.code == other.code

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        inner_code = "\n    ".join(self.code.text.split("\n"))
        code = f"def target():\n    {inner_code}"

        ctx = {}
        exec(code, ctx)

        mutable = MutableFunction(ctx["target"])
        builder = mutable.create_filled_builder()
        return builder.temporary_instructions

    def copy(self) -> "PythonCodeAssembly":
        return type(self)(self.code)
