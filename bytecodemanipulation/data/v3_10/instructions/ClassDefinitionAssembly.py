import typing

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.ClassDefinitionAssembly import (
    AbstractClassDefinitionAssembly,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


@Parser.register
class ClassDefinitionAssembly(AbstractClassDefinitionAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        inner_scope = scope.copy(sub_scope_name=self.name(scope), shared_locals=False)

        target = MutableFunction(lambda: None)

        inner_bytecode = [
            Instruction(Opcodes.LOAD_NAME, "__name__"),
            Instruction(Opcodes.STORE_NAME, "__module__"),
            Instruction(Opcodes.LOAD_CONST, self.name(scope)),
            Instruction(Opcodes.STORE_NAME, "__qualname__"),
        ]

        raw_inner_code = self.code_block.emit_bytecodes(target, inner_scope)

        for instr in raw_inner_code:
            if instr.opcode == Opcodes.LOAD_FAST:
                instr.change_opcode(Opcodes.LOAD_NAME, arg_value=instr.arg_value)
            elif instr.opcode == Opcodes.STORE_FAST:
                instr.change_opcode(Opcodes.STORE_NAME, arg_value=instr.arg_value)
            elif instr.opcode == Opcodes.DELETE_FAST:
                instr.change_opcode(Opcodes.DELETE_NAME, arg_value=instr.arg_value)

        inner_bytecode += raw_inner_code

        if inner_bytecode:
            inner_bytecode[-1].next_instruction = target.instruction_entry_point

        for i, instr in enumerate(inner_bytecode[:-1]):
            instr.next_instruction = inner_bytecode[i + 1]

        target.instruction_entry_point = inner_bytecode[0]
        target.reassign_to_function()

        code_obj = target.target.__code__

        bytecode = [
            Instruction(Opcodes.LOAD_BUILD_CLASS),
            Instruction(Opcodes.LOAD_CONST, code_obj),
            Instruction(Opcodes.LOAD_CONST, self.name(scope)),
            Instruction(Opcodes.MAKE_FUNCTION, arg=0),
            Instruction(Opcodes.LOAD_CONST, self.name(scope)),
        ]

        for parent in self.parents:
            bytecode += parent.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(Opcodes.CALL_FUNCTION, arg=2 + len(self.parents)),
            Instruction(Opcodes.STORE_FAST, self.name(scope)),
        ]
        return bytecode
