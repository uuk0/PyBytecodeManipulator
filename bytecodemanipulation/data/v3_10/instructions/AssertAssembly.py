import typing

from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.AssertAssembly import (
    AbstractAssertAssembly,
)


@Parser.register
class AssertAssembly(AbstractAssertAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        bytecode = self.source.emit_bytecodes(function, scope)

        end_label = scope.scope_name_generator("assert_success")

        bytecode += [
            Instruction(function, -1, Opcodes.POP_JUMP_IF_TRUE, JumpToLabel(end_label)),
        ]

        if self.text:
            bytecode += self.text.emit_bytecodes(function, scope)
        else:
            bytecode += [
                Instruction(function, -1, Opcodes.LOAD_CONST, "assertion failed")
            ]

        bytecode += [
            Instruction(function, -1, Opcodes.LOAD_CONST, AssertionError),
            Instruction(function, -1, Opcodes.ROT_TWO),
            Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=1),
            Instruction(function, -1, Opcodes.RAISE_VARARGS, arg=1),
            Instruction(function, -1, Opcodes.BYTECODE_LABEL, end_label),
        ]
        return bytecode
