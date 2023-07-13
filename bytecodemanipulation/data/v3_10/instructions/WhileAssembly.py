from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.WhileAssembly import (
    AbstractWhileAssembly,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class WHILEAssembly(AbstractWhileAssembly):
    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):
        name = (
            ":".join(e(scope) for e in self.label_name)
            if self.label_name is not None
            else None
        )

        if self.label_name is None:
            end = Instruction(Opcodes.NOP)
        else:
            end = Instruction(Opcodes.BYTECODE_LABEL, name + ":END")

        CONDITION = self.source.emit_bytecodes(function, scope)

        if self.label_name:
            CONDITION.insert(
                0,
                Instruction(Opcodes.BYTECODE_LABEL, name),
            )

        HEAD = Instruction("POP_JUMP_IF_FALSE", end)

        BODY = self.body.emit_bytecodes(function, scope)

        if self.label_name:
            BODY.insert(
                0,
                Instruction(
                    Opcodes.BYTECODE_LABEL,
                    name + ":INNER",
                ),
            )

        JUMP_BACK = Instruction("JUMP_ABSOLUTE", CONDITION[0])

        return CONDITION + [HEAD] + BODY + [JUMP_BACK, end]
