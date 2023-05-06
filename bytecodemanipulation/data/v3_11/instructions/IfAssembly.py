from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.IfAssembly import AbstractIFAssembly
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class IFAssembly(AbstractIFAssembly):
    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):

        if self.label_name is None:
            end = Instruction(function, -1, "NOP")
        else:
            end = Instruction(
                function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text + "_END"
            )

        return (
            (
                []
                if self.label_name is None
                else [
                    Instruction(
                        function,
                        -1,
                        Opcodes.BYTECODE_LABEL,
                        self.label_name.text + "_HEAD",
                    )
                ]
            )
            + self.source.emit_bytecodes(function, scope)
            + [Instruction(function, -1, "POP_JUMP_IF_FALSE", end)]
            + (
                []
                if self.label_name is None
                else [
                    Instruction(
                        function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text
                    )
                ]
            )
            + self.body.emit_bytecodes(function, scope)
            + [end]
        )
