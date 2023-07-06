import functools
import inspect
import typing

from bytecodemanipulation.assembler.AbstractBase import MacroExpandedIdentifier
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.data.shared.expressions.LocalAccessExpression import LocalAccessExpression
from bytecodemanipulation.data.shared.expressions.MacroParameterAcessExpression import MacroParameterAccessExpression
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
                scope.closure_locals.add(name(scope))

        local_variable_buffer = scope.scope_name_generator("outer_locals")

        target.argument_count = len(self.args)
        if self.bound_variables:
            target.argument_names.insert(0, local_variable_buffer)
            target.argument_count += 1

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

        has_yield_statement = False

        def rewrite_outer_access(instruction: Instruction):
            if instruction.opcode == Opcodes.LOAD_DEREF and instruction.arg_value in scope.closure_locals:
                instruction.insert_after([
                    Instruction(Opcodes.LOAD_FAST, local_variable_buffer),
                    Instruction(Opcodes.LOAD_CONST, instruction.arg_value),
                    Instruction(Opcodes.BINARY_SUBSCR),
                ])
                instruction.change_opcode(Opcodes.NOP)
            elif instruction.opcode == Opcodes.STORE_DEREF and instruction.arg_value in scope.closure_locals:
                instruction.insert_after([
                    Instruction(Opcodes.LOAD_FAST, local_variable_buffer),
                    Instruction(Opcodes.LOAD_CONST, instruction.arg_value),
                    Instruction(Opcodes.STORE_SUBSCR),
                ])
                instruction.change_opcode(Opcodes.NOP)
            elif instruction.opcode == Opcodes.DELETE_DEREF and instruction.arg_value in scope.closure_locals:
                instruction.insert_after([
                    Instruction(Opcodes.LOAD_FAST, local_variable_buffer),
                    Instruction(Opcodes.LOAD_CONST, instruction.arg_value),
                    Instruction(Opcodes.DELETE_SUBSCR),
                ])
                instruction.change_opcode(Opcodes.NOP)
            elif instruction.opcode in (Opcodes.YIELD_VALUE, Opcodes.YIELD_FROM):
                nonlocal has_yield_statement
                has_yield_statement = True

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(rewrite_outer_access))

        if has_yield_statement:
            target.code_flags |= inspect.CO_GENERATOR

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

        if self.bound_variables:
            # <function> = functools.partial(<function>, <bound local dict>)

            bytecode += [
                Instruction(Opcodes.LOAD_CONST, functools.partial),
                Instruction(Opcodes.ROT_TWO),
                Instruction(Opcodes.LOAD_CONST, inspect.currentframe),
                Instruction(Opcodes.CALL_FUNCTION, arg=0),
                Instruction(Opcodes.LOAD_ATTR, "f_locals"),
                Instruction(Opcodes.CALL_FUNCTION, arg=2),
            ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)
        elif not self.func_name:
            raise throw_positioned_error(
                scope,
                [],
                "Expected either 'target' or <valid name>",
            )
        else:
            bytecode += [
                Instruction(Opcodes.STORE_FAST, self.prefix + self.func_name(scope)),
            ]

        return bytecode
