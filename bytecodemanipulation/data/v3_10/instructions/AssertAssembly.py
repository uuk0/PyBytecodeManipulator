import typing

from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.opcodes.Opcodes import Opcodes
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Instruction import Instruction
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
            Instruction(Opcodes.POP_JUMP_IF_TRUE, JumpToLabel(end_label)),
        ]

        if self.text:
            bytecode += self.text.emit_bytecodes(function, scope)
        else:
            bytecode += [
                Instruction(Opcodes.LOAD_CONST, "assertion failed")
            ]

        bytecode += [
            Instruction(Opcodes.LOAD_CONST, AssertionError),
            Instruction(Opcodes.ROT_TWO),
            Instruction(Opcodes.CALL_FUNCTION, arg=1),
            Instruction(Opcodes.RAISE_VARARGS, arg=1),
            Instruction(Opcodes.BYTECODE_LABEL, end_label),
        ]
        return bytecode
