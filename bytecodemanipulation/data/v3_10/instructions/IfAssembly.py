from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.IfAssembly import AbstractIFAssembly
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class IFAssembly(AbstractIFAssembly):
    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):
        label_name = ":".join(e(scope) for e in self.label_name) if self.label_name is not None else None

        if label_name is None:
            end = Instruction(Opcodes.NOP)
        else:
            end = Instruction(
                Opcodes.BYTECODE_LABEL, label_name + ":END"
            )

        try:
            value = self.source.evaluate_static_value(scope)
        except:
            return (
                (
                    []
                    if label_name is None
                    else [
                        Instruction(
                            Opcodes.BYTECODE_LABEL,
                            label_name + ":HEAD",
                        )
                    ]
                )
                + self.source.emit_bytecodes(function, scope)
                + [Instruction("POP_JUMP_IF_FALSE", end)]
                + (
                    []
                    if label_name is None
                    else [
                        Instruction(
                            Opcodes.BYTECODE_LABEL, label_name
                        )
                    ]
                )
                + self.body.emit_bytecodes(function, scope)
                + [end]
            )

        if value:
            return (
                    (
                        []
                        if label_name is None
                        else [
                            Instruction(
                                Opcodes.BYTECODE_LABEL,
                                label_name + ":HEAD",
                            )
                        ]
                    )
                    + (
                        []
                        if label_name is None
                        else [
                            Instruction(
                                Opcodes.BYTECODE_LABEL, label_name
                            )
                        ]
                    )
                    + self.body.emit_bytecodes(function, scope)
                    + [end]
            )

        return (
                (
                    []
                    if label_name is None
                    else [
                        Instruction(
                            Opcodes.BYTECODE_LABEL,
                            label_name + ":HEAD",
                        )
                    ]
                )
                + (
                    []
                    if label_name is None
                    else [
                        Instruction(
                            Opcodes.BYTECODE_LABEL, label_name
                        )
                    ]
                )
                + [end]
        )
