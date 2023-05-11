import typing

from bytecodemanipulation.data.shared.instructions.FunctionDefinitionAssembly import (
    AbstractFunctionDefinitionAssembly,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.CallAssembly import (
    AbstractCallAssembly,
)
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.util import LambdaInstructionWalker


@Parser.register
class FunctionDefinitionAssembly(AbstractFunctionDefinitionAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        flags = 0
        bytecode = []

        inner_labels = self.body.collect_label_info(scope)
        label_targets = {}

        inner_scope = scope.copy()

        if self.bound_variables:
            if any(map(lambda e: e[1], self.bound_variables)):
                raise NotImplementedError("Static variables")

            names = [e[0](scope) for e in self.bound_variables]
            s = {}
            exec(
                f"{' = '.join(names)} = None\nresult = lambda: ({', '.join(names)})", s
            )
            tar = s["result"]
        else:
            tar = lambda: None

        target = MutableFunction(tar)
        inner_bytecode = []

        if self.bound_variables:
            for name, is_static in self.bound_variables:
                # print(name, name(scope), is_static)
                inner_bytecode += [
                    Instruction(target, -1, Opcodes.LOAD_DEREF, name(scope) + "%inner"),
                    Instruction(target, -1, Opcodes.STORE_DEREF, name(scope)),
                ]

        inner_bytecode += self.body.emit_bytecodes(target, inner_scope)
        inner_bytecode[-1].next_instruction = target.instructions[0]

        for i, instr in enumerate(inner_bytecode[:-1]):
            instr.next_instruction = inner_bytecode[i + 1]

        def walk_label(instruction: Instruction):
            if instruction.opcode == Opcodes.BYTECODE_LABEL:
                # print(instruction, instruction.next_instruction)
                label_targets[instruction.arg_value] = (
                    instruction.next_instruction
                    if instruction.next_instruction is not None
                    else instruction
                )
                instruction.change_opcode(Opcodes.NOP, update_next=False)

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(walk_label))

        def resolve_jump_to_label(ins: Instruction):
            if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
                ins.change_arg_value(label_targets[ins.arg_value.name])

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(resolve_jump_to_label))

        target.assemble_instructions_from_tree(inner_bytecode[0])
        del inner_bytecode

        has_kwarg = False
        for arg in self.args:
            if isinstance(arg, AbstractCallAssembly.IMPLEMENTATION.KwArg):
                has_kwarg = True
                break

        if has_kwarg:
            flags |= 0x02
            raise NotImplementedError("Kwarg defaults")

        if self.bound_variables:
            if any(map(lambda e: e[1], self.bound_variables)):
                raise NotImplementedError("Static variables")

            flags |= 0x08

            for name, is_static in self.bound_variables:
                bytecode += [
                    Instruction(function, -1, Opcodes.LOAD_FAST, name(scope)),
                    Instruction(
                        function, -1, Opcodes.STORE_DEREF, name(scope) + "%inner"
                    ),
                ]

            bytecode += [
                Instruction(function, -1, Opcodes.LOAD_CLOSURE, name(scope) + "%inner")
                for name, is_static in self.bound_variables
            ]
            bytecode.append(
                Instruction(
                    function, -1, Opcodes.BUILD_TUPLE, arg=len(self.bound_variables)
                )
            )

        target.argument_count = len(self.args)
        code_object = target.create_code_obj()

        bytecode += [
            Instruction(function, -1, "LOAD_CONST", code_object),
            Instruction(
                function,
                -1,
                "LOAD_CONST",
                self.func_name(scope) if self.func_name else "<lambda>",
            ),
            Instruction(function, -1, "MAKE_FUNCTION", arg=flags),
        ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)
        else:
            bytecode += [
                Instruction(function, -1, Opcodes.STORE_FAST, self.func_name(scope)),
            ]

        return bytecode
