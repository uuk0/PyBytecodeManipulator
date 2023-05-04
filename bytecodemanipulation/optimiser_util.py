import traceback
import typing
from bytecodemanipulation.annotated_std import CONSTANT_BUILTIN_TYPES
from bytecodemanipulation.annotated_std import CONSTANT_BUILTINS

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Opcodes import SIDE_EFFECT_FREE_LOADS
from bytecodemanipulation.Specialization import ArgDescriptor
from bytecodemanipulation.Specialization import MethodCallDescriptor
from bytecodemanipulation.Specialization import SpecializationContainer

OPCODE_TO_ATTR_SINGLE = {
    Opcodes.UNARY_POSITIVE: "__pos__",
    Opcodes.UNARY_NEGATIVE: "__neg__",
    Opcodes.UNARY_INVERT: "__invert__",
    Opcodes.UNARY_NOT: "__not__",
}

OPCODE_TO_ATTR_DOUBLE = {
    Opcodes.BINARY_MATRIX_MULTIPLY: "__matmul__",
    Opcodes.INPLACE_MATRIX_MULTIPLY: "__imatmul__",
    Opcodes.BINARY_POWER: "__pow__",
    Opcodes.INPLACE_POWER: "__ipow__",
    Opcodes.BINARY_MULTIPLY: "__mul__",
    Opcodes.INPLACE_MULTIPLY: "__imul__",
    Opcodes.BINARY_MODULO: "__mod__",
    Opcodes.INPLACE_MODULO: "__imod__",
    Opcodes.BINARY_ADD: "__add__",
    Opcodes.INPLACE_ADD: "__iadd__",
    Opcodes.BINARY_SUBTRACT: "__sub__",
    Opcodes.INPLACE_SUBTRACT: "__isub__",
    Opcodes.BINARY_SUBSCR: "__getitem__",
    Opcodes.BINARY_FLOOR_DIVIDE: "__floordiv__",
    Opcodes.INPLACE_FLOOR_DIVIDE: "__ifloordiv__",
    Opcodes.BINARY_TRUE_DIVIDE: "__truediv__",
    Opcodes.INPLACE_TRUE_DIVIDE: "__itruediv__",
    Opcodes.GET_LEN: "__len__",
    Opcodes.BINARY_LSHIFT: "__lshift__",
    Opcodes.INPLACE_LSHIFT: "__ilshift__",
    Opcodes.BINARY_RSHIFT: "__rshift__",
    Opcodes.INPLACE_RSHIFT: "__irshift__",
    Opcodes.BINARY_AND: "__and__",
    Opcodes.BINARY_XOR: "__xor__",
    Opcodes.BINARY_OR: "__or__",
    (Opcodes.IS_OP, 0): lambda a, b: a is b,
    (Opcodes.IS_OP, 1): lambda a, b: a is not b,
    (Opcodes.COMPARE_OP, 0): lambda a, b: a < b,
    (Opcodes.COMPARE_OP, 1): lambda a, b: a <= b,
    (Opcodes.COMPARE_OP, 2): lambda a, b: a == b,
    (Opcodes.COMPARE_OP, 3): lambda a, b: a != b,
    (Opcodes.COMPARE_OP, 4): lambda a, b: a > b,
    (Opcodes.COMPARE_OP, 5): lambda a, b: a >= b,
}


def inline_const_value_pop_pairs(mutable: MutableFunction) -> bool:
    dirty = False

    for instruction in mutable.instructions:
        if instruction.opcode == Opcodes.POP_TOP:
            try:
                # print("search")
                source = next(instruction.trace_stack_position(0))
            except StopIteration:
                # source = next(instruction.trace_stack_position(0))

                print("---")

                for instr in mutable.instructions:
                    print(instr)

                print("---")
                print(instruction)
                print(instruction.get_priorities_previous())
                raise

            # Inline LOAD_XX - POP pairs
            if source.opcode in SIDE_EFFECT_FREE_LOADS:
                instruction.change_opcode(Opcodes.NOP)
                source.change_opcode(Opcodes.NOP)
                return True

            # Inline CALL_XX (constant expr) - POP pairs
            if source.opcode == Opcodes.CALL_FUNCTION:
                func_resolve = next(source.trace_stack_position(source.arg))

                if func_resolve.opcode == Opcodes.LOAD_CONST:
                    function = func_resolve.arg_value

                    if function in CONSTANT_BUILTINS or (
                        hasattr(function, "_OPTIMISER_CONTAINER")
                        and getattr(
                            function, "_OPTIMISER_CONTAINER"
                        ).is_side_effect_free_op
                    ):
                        instruction.change_opcode(Opcodes.NOP)

                        if func_resolve.arg == 0:
                            func_resolve.change_opcode(Opcodes.NOP)
                            continue
                        pops = func_resolve.arg

                        func_resolve.change_opcode(Opcodes.POP_TOP)
                        pops -= 1

                        if not pops:
                            continue

                        for _ in range(pops):
                            nop = Instruction.create(Opcodes.NOP)
                            nop.next_instruction = func_resolve.next_instruction
                            func_resolve.next_instruction = nop

                        mutable.assemble_instructions_from_tree(
                            mutable.instructions[0].optimise_tree()
                        )
                        return True

            if source.opcode in (
                Opcodes.BUILD_LIST,
                Opcodes.BUILD_SET,
                Opcodes.BUILD_MAP,
            ):
                count = source.arg

                if source.opcode == Opcodes.BUILD_MAP:
                    count *= 2

                instruction.change_opcode(Opcodes.NOP)

                if count == 0:
                    source.change_opcode(Opcodes.NOP)
                    dirty = True
                    continue

                source.change_opcode(Opcodes.POP_TOP)

                if count == 1:
                    dirty = True
                    continue

                count -= 1

                for _ in range(count):
                    nop = Instruction.create(Opcodes.NOP)
                    nop.next_instruction = source.next_instruction
                    source.next_instruction = nop

                mutable.assemble_instructions_from_tree(
                    mutable.instructions[0].optimise_tree()
                )
                return True

    return dirty


def remove_local_var_assign_without_use(mutable: MutableFunction) -> bool:
    dirty = False

    last_loads_of_local = [-1] * len(mutable.shared_variable_names)

    for instruction in mutable.instructions:
        if instruction.opcode == Opcodes.LOAD_FAST:
            last_loads_of_local[instruction.arg] = instruction.offset

    for instruction in mutable.instructions:
        if (
            instruction.opcode in (Opcodes.STORE_FAST, Opcodes.DELETE_FAST)
            and last_loads_of_local[instruction.arg] < instruction.offset
        ):
            instruction.change_opcode(Opcodes.POP_TOP)
            dirty = True

    return dirty


def inline_constant_method_invokes(mutable: MutableFunction) -> bool:
    dirty = False

    for instr in mutable.instructions:
        if instr.opcode in (Opcodes.CALL_FUNCTION, Opcodes.CALL_METHOD):
            target = next(instr.trace_stack_position(instr.arg))

            if target.opcode == Opcodes.LOAD_CONST:
                function: typing.Callable = target.arg_value

                if function in CONSTANT_BUILTINS or (
                    hasattr(function, "_OPTIMISER_CONTAINER")
                    and getattr(function, "_OPTIMISER_CONTAINER").is_constant_op
                ):
                    args = [
                        next(instr.trace_stack_position(i))
                        for i in range(instr.arg - 1, -1, -1)
                    ]

                    if all(ins.opcode == Opcodes.LOAD_CONST for ins in args):
                        result = function(*(e.arg_value for e in args))

                        instr.change_opcode(Opcodes.LOAD_CONST)
                        instr.change_arg_value(result)
                        target.change_opcode(Opcodes.NOP)

                        for arg in args:
                            arg.change_opcode(Opcodes.NOP)

                        dirty = True

    return dirty


def inline_constant_binary_ops(mutable: MutableFunction) -> bool:
    dirty = False

    for instruction in mutable.instructions:
        if (
            instruction.opcode in OPCODE_TO_ATTR_SINGLE
            or (instruction.opcode, instruction.arg) in OPCODE_TO_ATTR_SINGLE
        ):
            method = OPCODE_TO_ATTR_SINGLE[
                instruction.opcode
                if instruction.opcode in OPCODE_TO_ATTR_SINGLE
                else (instruction.opcode, instruction.arg)
            ]

            target = next(instruction.trace_stack_position(0))

            if target.opcode == Opcodes.LOAD_CONST:
                value = target.arg_value

                if hasattr(value, method):
                    method = (
                        getattr(value, method) if isinstance(method, str) else method
                    )

                    if not callable(method) or not (
                        type(value) in CONSTANT_BUILTIN_TYPES
                        or (
                            hasattr(method, "_OPTIMISER_CONTAINER")
                            and getattr(method, "_OPTIMISER_CONTAINER").is_constant_op
                        )
                    ):
                        continue

                    try:
                        value = method()
                    except:
                        continue

                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(value)
                    target.change_opcode(Opcodes.NOP)
                    dirty = True

        elif (
            instruction.opcode in OPCODE_TO_ATTR_DOUBLE
            or (instruction.opcode, instruction.arg) in OPCODE_TO_ATTR_DOUBLE
        ):
            method = OPCODE_TO_ATTR_DOUBLE[
                instruction.opcode
                if instruction.opcode in OPCODE_TO_ATTR_DOUBLE
                else (instruction.opcode, instruction.arg)
            ]

            arg = next(instruction.trace_stack_position(1))
            target = next(instruction.trace_stack_position(0))

            if arg.opcode == target.opcode == Opcodes.LOAD_CONST:
                value = target.arg_value

                if isinstance(method, str):
                    method = getattr(value, method)

                    if not callable(method) or not (
                        type(value) in CONSTANT_BUILTIN_TYPES
                        or (
                            hasattr(method, "_OPTIMISER_CONTAINER")
                            and getattr(method, "_OPTIMISER_CONTAINER").is_constant_op
                        )
                    ):
                        continue

                try:
                    value = method(arg.arg_value, target.arg_value)
                except:
                    traceback.print_exc()
                    continue

                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(value)
                target.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)
                dirty = True

        elif instruction.opcode == Opcodes.BUILD_TUPLE:
            args = [
                next(instruction.trace_stack_position(i))
                for i in range(instruction.arg - 1, -1, -1)
            ]

            if all(instr.opcode == Opcodes.LOAD_CONST for instr in args):
                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(tuple(e.arg_value for e in args))

                for arg in args:
                    arg.change_opcode(Opcodes.NOP)

                dirty = True

        elif instruction.opcode == Opcodes.BUILD_SLICE:
            args = [
                next(instruction.trace_stack_position(i))
                for i in range(instruction.arg - 1, -1, -1)
            ]

            if all(instr.opcode == Opcodes.LOAD_CONST for instr in args):
                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(slice(*(e.arg_value for e in args)))

                for arg in args:
                    arg.change_opcode(Opcodes.NOP)

                dirty = True

        elif instruction.opcode == Opcodes.BUILD_STRING:
            args = [
                next(instruction.trace_stack_position(i))
                for i in range(instruction.arg - 1, -1, -1)
            ]

            if all(instr.opcode == Opcodes.LOAD_CONST for instr in args):
                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value("".join(e.arg_value for e in args))

                for arg in args:
                    arg.change_opcode(Opcodes.NOP)

                dirty = True

    return dirty


def remove_branch_on_constant(mutable: MutableFunction) -> bool:
    dirty = False

    for instruction in mutable.instructions:
        if (
            instruction.has_jump()
            and not instruction.has_unconditional_jump()
            and instruction.opcode not in (Opcodes.SETUP_FINALLY, Opcodes.SETUP_WITH)
        ):
            if instruction.previous_instructions is None:
                if (
                    instruction.offset == 0
                    and instruction.opcode == Opcodes.SETUP_FINALLY
                ):
                    continue

                raise RuntimeError

            source = next(instruction.trace_stack_position(0))

            if source.opcode == Opcodes.LOAD_CONST:
                flag = bool(source.arg_value)

                if instruction.opcode in (
                    Opcodes.JUMP_IF_TRUE_OR_POP,
                    Opcodes.JUMP_IF_FALSE_OR_POP,
                ):
                    if instruction.opcode == Opcodes.JUMP_IF_FALSE_OR_POP:
                        flag = not flag

                    if flag:
                        instruction.change_opcode(Opcodes.JUMP_ABSOLUTE)
                    else:
                        source.change_opcode(Opcodes.NOP)
                        instruction.change_opcode(Opcodes.NOP)

                    dirty = True

                    continue

                if instruction.opcode in (
                    Opcodes.POP_JUMP_IF_TRUE,
                    Opcodes.POP_JUMP_IF_FALSE,
                ):
                    flag = bool(source.arg_value)

                    if instruction.opcode == Opcodes.POP_JUMP_IF_FALSE:
                        flag = not flag

                    source.change_opcode(Opcodes.NOP)

                    if flag:
                        instruction.change_opcode(Opcodes.JUMP_ABSOLUTE)
                    else:
                        instruction.change_opcode(Opcodes.NOP)

                    dirty = True

    return dirty


def inline_static_attribute_access(mutable: MutableFunction) -> bool:
    dirty = False

    for instruction in mutable.instructions:
        if instruction.opcode in (Opcodes.LOAD_ATTR, Opcodes.LOAD_METHOD):
            source_instr = next(instruction.trace_stack_position(0))

            if source_instr.opcode == Opcodes.LOAD_CONST:
                source: typing.Any = source_instr.arg_value

                if hasattr(
                    source, "_OPTIMISER_CONTAINER"
                ) and source._OPTIMISER_CONTAINER.is_attribute_static(
                    instruction.arg_value
                ):
                    attr_name = instruction.arg_value
                    source_instr.change_opcode(Opcodes.NOP)
                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(getattr(source, attr_name))

                    # print(instruction)

                    use = next(instruction.trace_stack_position_use(0))

                    if use.opcode == Opcodes.CALL_METHOD:
                        use.change_opcode(Opcodes.CALL_FUNCTION)

                    dirty = True

    return dirty


def apply_specializations(mutable: MutableFunction) -> bool:
    from bytecodemanipulation.Optimiser import _OptimisationContainer

    dirty = False

    for instruction in mutable.instructions:
        if instruction.opcode in (Opcodes.CALL_FUNCTION, Opcodes.CALL_METHOD):
            load_stack_pos = instruction.arg
            source = instruction.trace_normalized_stack_position(load_stack_pos)
            safe_source = next(instruction.trace_stack_position(load_stack_pos))

            if source and source.opcode == Opcodes.LOAD_CONST:
                container = _OptimisationContainer.get_for_target(source.arg_value)

                if not container.specializations:
                    continue

                target_func = source.arg_value

                spec = SpecializationContainer()
                spec.target = mutable
                spec.underlying_function = target_func
                spec.method_call_descriptor = MethodCallDescriptor(
                    safe_source, instruction
                )
                spec.set_arg_descriptors(
                    [
                        ArgDescriptor(
                            next(instruction.trace_stack_position(arg_id)),
                            instruction.trace_normalized_stack_position(arg_id),
                            arg_id,
                        )
                        for arg_id in range(instruction.arg - 1, -1, -1)
                    ]
                )

                for special in container.specializations:
                    special(spec)

                    if spec.no_special:
                        continue

                    spec.apply()
                    dirty = True
                    break

    return dirty


def remove_nops(mutable: MutableFunction):
    root = mutable.instructions[0]
    root = root.optimise_tree()
    mutable.assemble_instructions_from_tree(root)
