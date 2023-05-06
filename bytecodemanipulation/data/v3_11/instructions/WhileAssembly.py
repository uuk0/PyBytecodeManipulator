from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.WhileAssembly import (
    AbstractWhileAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class WHILEAssembly(AbstractWhileAssembly):
    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):
        if self.label_name is None:
            end = Instruction(function, -1, "NOP")
        else:
            end = Instruction(
                function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text + "_END"
            )

        CONDITION = self.source.emit_bytecodes(function, scope)

        if self.label_name:
            CONDITION.insert(
                0,
                Instruction(function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text),
            )

        HEAD = Instruction(function, -1, "POP_JUMP_IF_FALSE", end)

        BODY = self.body.emit_bytecodes(function, scope)

        if self.label_name:
            BODY.insert(
                0,
                Instruction(
                    function,
                    -1,
                    Opcodes.BYTECODE_LABEL,
                    self.label_name.text + "_INNER",
                ),
            )

        JUMP_BACK = Instruction(function, -1, "JUMP_ABSOLUTE", CONDITION[0])

        return CONDITION + [HEAD] + BODY + [JUMP_BACK, end]
