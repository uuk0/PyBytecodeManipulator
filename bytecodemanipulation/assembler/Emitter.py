import string
import types
import typing

from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor, StaticIdentifier
from bytecodemanipulation.assembler.Lexer import Lexer
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes
from bytecodemanipulation.assembler.Parser import (
    Parser as AssemblyParser,
)
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel, ParsingScope
from bytecodemanipulation.assembler import target as assembly_targets


def _visit_for_stack_effect(
    ins: Instruction,
    eff_a: typing.Tuple[int, int] | None,
    eff_b: typing.Tuple[int, int] | None,
) -> typing.Tuple[int, int]:
    if ins.opcode == Opcodes.FOR_ITER:
        raise RuntimeError

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


def apply_inline_assemblies(
    target: MutableFunction | typing.Callable, store_at_target: bool = None
):
    """
    Processes all assembly() calls, label() calls and jump() calls in 'target'
    """
    if not isinstance(target, MutableFunction):
        target = MutableFunction(target)
        if store_at_target is None:
            store_at_target = True

    labels: typing.Set[IIdentifierAccessor] = set()
    label_targets: typing.Dict[str, Instruction] = {}
    insertion_points: typing.List[typing.Tuple[str, Instruction]] = []

    def visit(instr: Instruction):
        if instr.opcode == Opcodes.LOAD_GLOBAL:
            try:
                value = target.target.__globals__.get(instr.arg_value)
            except KeyError:
                return

            if value == assembly_targets.assembly:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))

                if arg.opcode != Opcodes.LOAD_CONST:
                    raise SyntaxError("<assembly> must be constant!")

                if invoke.next_instruction.opcode == Opcodes.POP_TOP:
                    insertion_points.append((typing.cast(str, arg.arg_value), invoke.next_instruction))
                else:
                    insertion_points.append((typing.cast(str, arg.arg_value), invoke))

                instr.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)
                invoke.change_opcode(Opcodes.LOAD_CONST, None)

            elif value == assembly_targets.jump:
                invoke = next(instr.trace_stack_position_use(0))

                if invoke.arg not in (1, 2):
                    raise SyntaxError(f"expected one to two args, not {invoke.arg} for <jump>")

                label_name = next(invoke.trace_stack_position(0))

                if label_name.opcode != Opcodes.LOAD_CONST:
                    raise SyntaxError(f"expected <constant>, got {label_name}")

                condition = None
                if invoke.arg == 2:
                    condition = label_name
                    label_name = next(invoke.trace_stack_position(0))

                    if label_name.opcode != Opcodes.LOAD_CONST:
                        raise SyntaxError(f"expected <constant>, got {label_name}")

                    raise NotImplementedError("<condition> on jump() target")

                if not typing.cast(str, label_name.arg_value).isalnum():
                    raise SyntaxError("label name only characters and digits are allowed for label names!")

                if invoke.next_instruction.opcode == Opcodes.POP_TOP:
                    insertion_points.append(
                        (f"JUMP {label_name.arg_value}", invoke.next_instruction)
                    )
                else:
                    raise SyntaxError(invoke.next_instruction)

                instr.change_opcode(Opcodes.NOP)
                label_name.change_opcode(Opcodes.NOP)
                invoke.change_opcode(Opcodes.LOAD_CONST, None)

            elif value == assembly_targets.label:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))

                if arg.opcode != Opcodes.LOAD_CONST:
                    raise SyntaxError("<label name> must be constant")

                labels.add(StaticIdentifier(typing.cast(str, arg.arg_value)))
                invoke.change_opcode(Opcodes.BYTECODE_LABEL, arg.arg_value)
                invoke.insert_after(Instruction.create_with_same_info(invoke, Opcodes.LOAD_CONST, None))
                instr.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)
                label_targets[typing.cast(str, invoke.arg_value)] = invoke.next_instruction

    target.walk_instructions(visit)

    if not insertion_points:
        raise RuntimeError("no target found!")

    scope = ParsingScope()
    scope.globals_dict = target.target.__globals__
    scope.module_file = target.target.__globals__["__file__"]
    scope.filled_locals = set(target.argument_names)

    def visit(instr: Instruction):
        if instr.opcode == Opcodes.STORE_FAST:
            scope.filled_locals.add(instr.arg_value)


    target.walk_instructions(visit)

    if target.target.__module__ in GLOBAL_SCOPE_CACHE:
        scope.global_scope = GLOBAL_SCOPE_CACHE[target.target.__module__]
    else:
        GLOBAL_SCOPE_CACHE[target.target.__module__] = scope.global_scope

    assemblies = [
        AssemblyParser(
            Lexer(code).add_line_offset(instr.source_location[0] + 1).lex(),
            scope.scope_path.clear() or scope,
        ).parse()
        for code, instr in insertion_points
    ]

    for asm in assemblies:
        asm_labels = asm.collect_label_info(scope)
        labels.update({StaticIdentifier(e) for e in asm_labels})

    scope.labels |= labels

    max_stack_effects = []

    # for asm in assemblies:
    #     asm.fill_scope_complete(scope)

    scope.scope_path.clear()

    for (_, instr), asm in zip(insertion_points, assemblies):
        _create_fragment_bytecode(asm, instr, label_targets, max_stack_effects, scope, target)

    target.walk_instructions(visit)

    pending: typing.List[Instruction] = []

    def resolve_special_code(ins: Instruction):
        # print(ins)
        if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
            if ins.arg_value.name not in label_targets:
                print(label_targets)
                raise NameError(f"Label '{ins.arg_value.name}' not found!")

            ins.change_arg_value(label_targets[ins.arg_value.name])
            pending.append(ins.arg_value)

        elif ins.opcode == Opcodes.STATIC_ATTRIBUTE_ACCESS:
            source = next(ins.trace_stack_position(0))

            if source.opcode != Opcodes.LOAD_CONST:
                raise RuntimeError("expected 'constant' for constant attribute access!")

            obj = source.arg_value
            source.change_opcode(Opcodes.NOP)
            ins.change_opcode(
                Opcodes.LOAD_CONST, getattr(obj, ins.arg_value)
            )

    target.walk_instructions(resolve_special_code)

    if store_at_target:
        target.reassign_to_function()

    return target


def _create_fragment_bytecode(asm, insertion_point: Instruction, label_targets: typing.Dict[str, Instruction], max_stack_effects: typing.List, scope: ParsingScope, target: MutableFunction):
    bytecode = asm.create_bytecode(target, scope)

    if bytecode:
        # link the instructions to each other
        for i, ins in enumerate(bytecode[:-1]):
            ins.next_instruction = bytecode[i + 1]

        try:
            stack_effect, max_stack_effect = bytecode[0].apply_value_visitor(
                _visit_for_stack_effect
            )
        except RuntimeError:
            stack_effect = 0
            max_stack_effect = 0

    else:
        max_stack_effects.append(0)
        return

    if (
        stack_effect != 0
        and not (
            bytecode[-1].has_unconditional_jump() or bytecode[-1].has_stop_flow()
        )
    ):
        # print(asm)

        total = 0

        for e in enumerate(bytecode):
            add, subtract, _ = e[1].get_stack_affect()
            total += add - subtract
            print(*e, total)

        print(stack_effect)

        raise RuntimeError(
            f"Inline assembly code mustn't change overall stack size at exit, got a delta of {stack_effect}!"
        )

    max_stack_effects.append(max_stack_effect)

    for i, ins in enumerate(bytecode[:-1]):
        if not ins.has_stop_flow() and not ins.has_unconditional_jump():
            ins.next_instruction = bytecode[i + 1]

    bytecode[-1].next_instruction = following_instr = insertion_point.next_instruction

    insertion_point.insert_after(bytecode)

    for i, ins in enumerate(bytecode):
        if ins.opcode == Opcodes.BYTECODE_LABEL:
            label_targets[ins.arg_value] = ins.next_instruction

            if not isinstance(ins, Instruction):
                print("error: ", ins)

            ins.change_opcode(Opcodes.NOP)
            ins.next_instruction = (
                bytecode[i + 1] if i < len(bytecode) - 1 else following_instr
            )


def execute_module_in_instance(
    asm_code: str, module: types.ModuleType, file: str = None
):
    scope = ParsingScope()

    try:
        scope.module_file = file or module.__file__
    except AttributeError:
        pass

    if module.__name__ in GLOBAL_SCOPE_CACHE:
        scope.global_scope = GLOBAL_SCOPE_CACHE[module.__name__]
    else:
        GLOBAL_SCOPE_CACHE[module.__name__] = scope.global_scope

    asm = AssemblyParser(asm_code, scope).parse()
    scope.labels = asm.get_labels(scope)
    # asm.fill_scope_complete(scope)
    scope.scope_path.clear()
    create_function = lambda m: None
    target = MutableFunction(create_function)
    target.argument_names[0] = "$module$"

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

    if not bytecode:
        bytecode.append(Instruction(Opcodes.NOP))

    bytecode[-1].next_instruction = target.instruction_entry_point
    target.instruction_entry_point = bytecode[0]
    target.prepare_previous_instructions()

    target.walk_instructions(resolve_jump_to_label)

    def visit(instr):
        if instr.opcode == Opcodes.STORE_FAST:
            load_module = Instruction.create_with_same_info(instr, Opcodes.LOAD_FAST, "$module$")
            store = Instruction.create_with_same_info(instr, Opcodes.STORE_ATTR, instr.arg_value)

            instr.change_opcode(Opcodes.NOP)
            instr.insert_after([load_module, store])

        elif instr.opcode == Opcodes.LOAD_FAST:
            load_module = Instruction.create_with_same_info(instr, Opcodes.LOAD_FAST, "$module$")
            load = Instruction.create_with_same_info(instr, Opcodes.LOAD_ATTR, instr.arg_value)

            instr.change_opcode(Opcodes.NOP)
            instr.insert_after([load_module, load])

        elif instr.opcode == Opcodes.DELETE_FAST:
            load_module = Instruction.create_with_same_info(instr, Opcodes.LOAD_FAST, "$module$")
            delete = Instruction.create_with_same_info(instr, Opcodes.DELETE_ATTR, instr.arg_value)

            instr.change_opcode(Opcodes.NOP)
            instr.insert_after([load_module, delete])

    target.walk_instructions_stable(visit)

    target.function_name = module.__name__
    target.reassign_to_function()

    create_function(module)
