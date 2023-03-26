import dis
import string
import types
import typing

import bytecodemanipulation.assembler.Lexer
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.assembler.Parser import (
    Parser as AssemblyParser,
    JumpToLabel,
    ParsingScope,
)
from bytecodemanipulation.assembler import target as assembly_targets
from bytecodemanipulation.util import LambdaInstructionWalker


def _visit_for_stack_effect(
    ins: Instruction,
    eff_a: typing.Tuple[int, int] | None,
    eff_b: typing.Tuple[int, int] | None,
) -> typing.Tuple[int, int]:
    eff = 0
    max_size = 0

    if eff_b is not None:
        max_size = eff_b[1]

    if eff_a is not None:
        eff += eff_a[0]

        max_size = max(max_size, eff, eff_a[0])

    push, pop, *_ = ins.get_stack_affect()

    eff += push - pop

    max_size = max(max_size, max_size + eff)

    return eff, max_size


GLOBAL_SCOPE_CACHE: typing.Dict[str, dict] = {}


def apply_inline_assemblies(target: MutableFunction):
    """
    Processes all assembly() calls and label() calls in 'target'
    """

    labels = set()
    insertion_points: typing.List[typing.Tuple[str, Instruction]] = []

    for instr in target.instructions[:]:
        if instr.opcode == Opcodes.LOAD_GLOBAL:
            try:
                value = target.target.__globals__.get(instr.arg_value)
            except KeyError:
                continue

            if value == assembly_targets.assembly:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))
                assert (
                    arg.opcode == Opcodes.LOAD_CONST
                ), "only constant assembly code is allowed!"

                if invoke.next_instruction.opcode == Opcodes.POP_TOP:
                    insertion_points.append((arg.arg_value, invoke.next_instruction))
                else:
                    insertion_points.append((arg.arg_value, invoke))

                instr.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)
                invoke.change_opcode(Opcodes.LOAD_CONST, None)

            elif value == assembly_targets.jump:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))
                assert (
                    arg.opcode == Opcodes.LOAD_CONST
                ), "only constant assembly code is allowed!"
                assert all(
                    e in string.ascii_letters + string.digits for e in arg.arg_value
                ), "only characters and digits are allowed for label names!"

                if invoke.next_instruction.opcode == Opcodes.POP_TOP:
                    insertion_points.append(
                        (f"JUMP {arg.arg_value}", invoke.next_instruction)
                    )
                else:
                    insertion_points.append((f"JUMP {arg.arg_value}", invoke))

                instr.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)
                invoke.change_opcode(Opcodes.LOAD_CONST, None)

            elif value == assembly_targets.label:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))
                assert (
                    arg.opcode == Opcodes.LOAD_CONST
                ), "only constant label names are allowed!"

                labels.add(arg.arg_value)
                invoke.change_opcode(Opcodes.BYTECODE_LABEL, arg.arg_value)
                invoke.insert_after(Instruction(target, -1, Opcodes.LOAD_CONST, None))
                instr.change_opcode(Opcodes.NOP)
                print(type(arg))
                arg.change_opcode(Opcodes.NOP)

    scope = ParsingScope()

    if target.target.__module__ in GLOBAL_SCOPE_CACHE:
        scope.global_scope = GLOBAL_SCOPE_CACHE[target.target.__module__]
    else:
        GLOBAL_SCOPE_CACHE[target.target.__module__] = scope.global_scope

    assemblies = [
        AssemblyParser(
            bytecodemanipulation.assembler.Lexer.Lexer(code)
            .add_line_offset(
                instr.source_location[0]
                if instr.source_location and instr.source_location[0]
                else 0
            )
            .lex(),
            scope.scope_path.clear() or scope,
        ).parse()
        for code, instr in insertion_points
    ]

    for asm in assemblies:
        labels.update(asm.collect_label_info())

    scope.labels |= labels

    max_stack_effects = []

    label_targets: typing.Dict[str, Instruction] = {}

    # for asm in assemblies:
    #     asm.fill_scope_complete(scope)

    scope.scope_path.clear()

    for (_, instr), asm in zip(insertion_points, assemblies):
        bytecode = asm.create_bytecode(target, scope)

        for i, ins in enumerate(bytecode[:-1]):
            ins.next_instruction = bytecode[i + 1]

        print("----")
        for e in bytecode:
            print(e)

        if bytecode:
            stack_effect, max_stack_effect = bytecode[0].apply_value_visitor(
                _visit_for_stack_effect
            )
        else:
            stack_effect = max_stack_effect = 0

        if (
            stack_effect != 0
            and bytecode
            and not (
                bytecode[-1].has_unconditional_jump() or bytecode[-1].has_stop_flow()
            )
        ):
            print(asm)

            for e in enumerate(bytecode):
                print(*e)

            raise RuntimeError(
                f"Inline assembly code mustn't change overall stack size at exit, got a delta of {stack_effect}!"
            )

        max_stack_effects.append(max_stack_effect)

        if bytecode:
            print("inserting AFTER", instr)
            instr.insert_after(bytecode)

        for ins in bytecode:
            if ins.opcode == Opcodes.BYTECODE_LABEL:
                label_targets[ins.arg_value] = ins.next_instruction
                ins.change_opcode(Opcodes.NOP)

    for ins in target.instructions:
        if ins.opcode == Opcodes.BYTECODE_LABEL:
            label_targets[ins.arg_value] = ins.next_instruction
            ins.change_opcode(Opcodes.NOP)

    def resolve_jump_to_label(ins: Instruction):
        if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
            ins.change_arg_value(label_targets[ins.arg_value.name])

    target.instructions[0].apply_visitor(LambdaInstructionWalker(resolve_jump_to_label))

    target.stack_size += max(max_stack_effects)

    # target.instructions[0].apply_value_visitor(lambda instr, *_: print(instr))

    target.assemble_instructions_from_tree(target.instructions[0])

    return target


def execute_module_in_instance(asm_code: str, module: types.ModuleType):
    scope = ParsingScope()

    if module.__name__ in GLOBAL_SCOPE_CACHE:
        scope.global_scope = GLOBAL_SCOPE_CACHE[module.__name__]
    else:
        GLOBAL_SCOPE_CACHE[module.__name__] = scope.global_scope

    asm = AssemblyParser(asm_code, scope).parse()
    scope.labels = asm.get_labels()
    # asm.fill_scope_complete(scope)
    scope.scope_path.clear()
    create_function = lambda m: None
    target = MutableFunction(create_function)
    target.shared_variable_names[0] = "$module$"
    bytecode = asm.create_bytecode(target, scope)

    if bytecode is None:
        return

    label_targets = {}
    for ins in bytecode:
        if ins.opcode == Opcodes.BYTECODE_LABEL:
            label_targets[ins.arg_value] = ins.next_instruction
            ins.change_opcode(Opcodes.NOP)

    for i, ins in enumerate(bytecode[:-1]):
        ins.next_instruction = bytecode[i + 1]

    def resolve_jump_to_label(ins: Instruction):
        if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
            ins.change_arg_value(label_targets[ins.arg_value.name])

    for instr in bytecode:
        instr.update_owner(
            target, -1, force_change_arg_index=True, update_following=False
        )

    if not bytecode:
        bytecode.append(Instruction(target, -1, "NOP"))

    bytecode[-1].next_instruction = target.instructions[0]
    target.assemble_instructions_from_tree(bytecode[0])

    target.instructions[0].apply_visitor(LambdaInstructionWalker(resolve_jump_to_label))
    target.stack_size = bytecode[0].apply_value_visitor(_visit_for_stack_effect)[1]

    target.assemble_instructions_from_tree(target.instructions[0])

    for instr in target.instructions:
        if instr.opcode == Opcodes.STORE_FAST:
            load_module = Instruction(target, -1, Opcodes.LOAD_FAST, "$module$")
            store = Instruction(target, -1, Opcodes.STORE_ATTR, instr.arg_value)

            instr.change_opcode(Opcodes.NOP)
            instr.insert_after([load_module, store])

        elif instr.opcode == Opcodes.LOAD_FAST:
            load_module = Instruction(target, -1, Opcodes.LOAD_FAST, "$module$")
            load = Instruction(target, -1, Opcodes.LOAD_ATTR, instr.arg_value)

            instr.change_opcode(Opcodes.NOP)
            instr.insert_after([load_module, load])

        elif instr.opcode == Opcodes.DELETE_FAST:
            load_module = Instruction(target, -1, Opcodes.LOAD_FAST, "$module$")
            delete = Instruction(target, -1, Opcodes.DELETE_ATTR, instr.arg_value)

            instr.change_opcode(Opcodes.NOP)
            instr.insert_after([load_module, delete])

    target.assemble_instructions_from_tree(target.instructions[0])
    target.function_name = module.__name__

    target.reassign_to_function()

    # dis.dis(target)

    create_function(module)
