from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.IfAssembly import AbstractIFAssembly
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class IFAssembly(AbstractIFAssembly):
    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):

        if self.label_name is None:
            end = Instruction(Opcodes.NOP)
        else:
            end = Instruction(
                Opcodes.BYTECODE_LABEL, self.label_name.text + "_END"
            )

        return (
            (
                []
                if self.label_name is None
                else [
                    Instruction(
                        Opcodes.BYTECODE_LABEL,
                        self.label_name.text + "_HEAD",
                    )
                ]
            )
            + self.source.emit_bytecodes(function, scope)
            + [Instruction("POP_JUMP_IF_FALSE", end)]
            + (
                []
                if self.label_name is None
                else [
                    Instruction(
                        Opcodes.BYTECODE_LABEL, self.label_name.text
                    )
                ]
            )
            + self.body.emit_bytecodes(function, scope)
            + [end]
        )
