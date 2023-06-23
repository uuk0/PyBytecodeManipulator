import typing

from bytecodemanipulation.data.shared.instructions.FunctionDefinitionAssembly import (
    AbstractFunctionDefinitionAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.CallAssembly import CallAssembly
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.CallAssembly import (
    AbstractCallAssembly,
)
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes
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

        inner_scope = scope.copy(shared_locals=False)

        for arg in self.args:
            if not isinstance(arg, (CallAssembly.Arg, CallAssembly.KwArg)):
                inner_scope.filled_locals.add(arg.name(scope))

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
                    Instruction(Opcodes.LOAD_DEREF, name(scope) + "%inner"),
                    Instruction(Opcodes.STORE_DEREF, name(scope)),
                ]

        inner_bytecode += self.body.emit_bytecodes(target, inner_scope)
        inner_bytecode[-1].next_instruction = target.instruction_entry_point

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
                instruction.change_opcode(Opcodes.NOP)

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(walk_label))

        def resolve_jump_to_label(ins: Instruction):
            if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
                ins.change_arg_value(label_targets[ins.arg_value.name])

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(resolve_jump_to_label))

        target.instruction_entry_point = inner_bytecode[0]
        del inner_bytecode

        has_kwarg = False
        for arg in self.args:
            if isinstance(arg, AbstractCallAssembly.IMPLEMENTATION.KwArg):
                has_kwarg = True
                break

        if has_kwarg:
            flags |= 0x01

            defaults = []
            c = 0

            for arg in self.args:
                if isinstance(arg, CallAssembly.KwArg):
                    defaults += typing.cast(CallAssembly.KwArg, arg).source.emit_bytecodes(function, scope)
                    c += 1

            defaults += [
                Instruction(Opcodes.BUILD_TUPLE, arg=c),
            ]

            bytecode += defaults

        if self.bound_variables:
            if any(map(lambda e: e[1], self.bound_variables)):
                raise NotImplementedError("Static variables")

            flags |= 0x08

            for name, is_static in self.bound_variables:
                bytecode += [
                    Instruction(Opcodes.LOAD_FAST, name(scope)),
                    Instruction(
                        Opcodes.STORE_DEREF, name(scope) + "%inner"
                    ),
                ]

            bytecode += [
                Instruction(Opcodes.LOAD_CLOSURE, name(scope) + "%inner")
                for name, is_static in self.bound_variables
            ]
            bytecode.append(
                Instruction(
                    Opcodes.BUILD_TUPLE, arg=len(self.bound_variables)
                )
            )

        target.argument_count = len(self.args)

        for arg in self.args:
            if isinstance(arg, CallAssembly.Arg):
                target.argument_names.append(arg.source(scope))
            elif isinstance(arg, CallAssembly.KwArg):
                target.argument_names.append(arg.key(scope))

        target.prepare_previous_instructions()
        code_object = target.create_code_obj()

        bytecode += [
            Instruction(Opcodes.LOAD_CONST, code_object),
            Instruction(
                Opcodes.LOAD_CONST,
                self.func_name(scope) if self.func_name else "<lambda>",
            ),
            Instruction(Opcodes.MAKE_FUNCTION, arg=flags),
        ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)
        else:
            bytecode += [
                Instruction(Opcodes.STORE_FAST, self.prefix + self.func_name(scope)),
            ]

        return bytecode
