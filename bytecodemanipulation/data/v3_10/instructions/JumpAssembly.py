import typing

from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.JumpAssembly import (
    AbstractJumpAssembly,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class JumpAssembly(AbstractJumpAssembly):
    # JUMP <label name> [(IF <condition access>) | ('(' <expression> | <op expression> ')')]

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        label_name = ":".join(e(scope) for e in self.label_name_token)

        if not scope.exists_label(label_name):
            raise ValueError(f"Label '{label_name}' is not valid in this context!")

        if self.condition is None:
            return [
                Instruction(
                    Opcodes.JUMP_ABSOLUTE,
                    JumpToLabel(label_name),
                )
            ]

        return self.condition.emit_bytecodes(function, scope) + [
            Instruction(
                Opcodes.POP_JUMP_IF_TRUE,
                JumpToLabel(label_name),
            )
        ]
