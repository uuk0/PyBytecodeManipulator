import typing

from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.JumpAssembly import (
    AbstractJumpAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class JumpAssembly(AbstractJumpAssembly):
    # JUMP <label name> [(IF <condition access>) | ('(' <expression> | <op expression> ')')]

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if not scope.exists_label(self.label_name_token.text):
            raise ValueError(
                f"Label '{self.label_name_token.text}' is not valid in this context!"
            )

        if self.condition is None:
            return [
                Instruction(
                    function,
                    -1,
                    Opcodes.JUMP_ABSOLUTE,
                    JumpToLabel(self.label_name_token.text),
                )
            ]

        return self.condition.emit_bytecodes(function, scope) + [
            Instruction(
                function,
                -1,
                Opcodes.POP_JUMP_IF_TRUE,
                JumpToLabel(self.label_name_token.text),
            )
        ]
