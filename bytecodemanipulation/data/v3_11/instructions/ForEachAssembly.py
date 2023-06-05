import typing

from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.ForEachAssembly import (
    AbstractForEachAssembly,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class ForEachAssembly(AbstractForEachAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if len(self.variables) != 1:
            bytecode = [
                Instruction.create_with_token(
                    self.base_token, Opcodes.LOAD_CONST, zip
                ),
            ]
        else:
            bytecode = []

        for source in self.sources:
            bytecode += source.emit_bytecodes(function, scope)

        loop_label_name_enter = scope.scope_name_generator("foreach_loop_enter")
        loop_label_name_exit = scope.scope_name_generator("foreach_loop_exit")

        if len(self.variables) != 1:
            bytecode += [
                Instruction.create_with_token(
                    self.base_token,
                    Opcodes.CALL_FUNCTION,
                    arg=len(self.sources),
                ),
                Instruction.create_with_token(
                    self.base_token, Opcodes.GET_ITER
                ),
                Instruction.create_with_token(
                    self.base_token,
                    Opcodes.BYTECODE_LABEL,
                    loop_label_name_enter,
                ),
                Instruction.create_with_token(
                    self.base_token,
                    Opcodes.FOR_ITER,
                    JumpToLabel(loop_label_name_exit),
                ),
                Instruction.create_with_token(
                    self.base_token,
                    Opcodes.UNPACK_SEQUENCE,
                    arg=len(self.sources),
                ),
            ]
        else:
            bytecode += [
                Instruction.create_with_token(
                    self.base_token, Opcodes.GET_ITER
                ),
                Instruction.create_with_token(
                    self.base_token,
                    Opcodes.BYTECODE_LABEL,
                    loop_label_name_enter,
                ),
                Instruction.create_with_token(
                    self.base_token,
                    Opcodes.FOR_ITER,
                    JumpToLabel(loop_label_name_exit),
                ),
            ]

        for var in self.variables:
            bytecode += var.emit_store_bytecodes(function, scope)

        bytecode += self.body.emit_bytecodes(function, scope)

        bytecode += [
            Instruction.create_with_token(
                self.base_token,
                Opcodes.JUMP_ABSOLUTE,
                JumpToLabel(loop_label_name_enter),
            ),
            Instruction.create_with_token(
                self.base_token,
                Opcodes.BYTECODE_LABEL,
                loop_label_name_exit,
            ),
        ]

        return bytecode
