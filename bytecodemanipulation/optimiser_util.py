import traceback
import typing

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.MutableFunctionHelpers import MutableFunctionWithTree

CONSTANT_BUILTINS = [
    min,
    max,
    int,
    str,
    float,
    tuple,
    complex,
    abs,
]

CONSTANT_BUILTIN_TYPES = [
    int,
    float,
    tuple,
    complex,
]


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


def inline_constant_method_invokes(mutable: MutableFunction) -> bool:
    dirty = False

    for instruction in mutable.instructions:
        if instruction.opcode == Opcodes.CALL_FUNCTION:
            target = mutable.trace_stack_position(
                instruction.offset, instruction.arg
            )

            if target.opcode == Opcodes.LOAD_CONST:
                function: typing.Callable = target.arg_value

                if function in CONSTANT_BUILTINS or (
                    hasattr(function, "_OPTIMISER_CONTAINER")
                    and getattr(function, "_OPTIMISER_CONTAINER").is_constant_op
                ):
                    args = [
                        mutable.trace_stack_position(instruction.offset, i)
                        for i in range(instruction.arg - 1, -1, -1)
                    ]

                    if all(instr.opcode == Opcodes.LOAD_CONST for instr in args):
                        result = function(*(e.arg_value for e in args))

                        instruction.change_opcode(Opcodes.LOAD_CONST)
                        instruction.change_arg_value(result)
                        target.change_opcode(Opcodes.NOP)

                        for arg in args:
                            arg.change_opcode(Opcodes.NOP)

                        dirty = True

    return dirty


def inline_constant_binary_ops(mutable: MutableFunction) -> bool:
    dirty = False

    for instruction in mutable.instructions:
        if instruction.opcode in OPCODE_TO_ATTR_SINGLE or (instruction.opcode, instruction.arg) in OPCODE_TO_ATTR_SINGLE:
            method = OPCODE_TO_ATTR_SINGLE[instruction.opcode if instruction.opcode in OPCODE_TO_ATTR_SINGLE else (instruction.opcode, instruction.arg)]

            target = mutable.trace_stack_position(instruction.offset, 0)

            if target.opcode == Opcodes.LOAD_CONST:
                value = target.arg_value

                if hasattr(value, method):
                    method = getattr(value, method) if isinstance(method, str) else method

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

        elif instruction.opcode in OPCODE_TO_ATTR_DOUBLE or (instruction.opcode, instruction.arg) in OPCODE_TO_ATTR_DOUBLE:
            method = OPCODE_TO_ATTR_DOUBLE[instruction.opcode if instruction.opcode in OPCODE_TO_ATTR_DOUBLE else (instruction.opcode, instruction.arg)]

            arg = mutable.trace_stack_position(instruction.offset, 1)
            target = mutable.trace_stack_position(instruction.offset, 0)

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
                mutable.trace_stack_position(instruction.offset, i)
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
                mutable.trace_stack_position(instruction.offset, i)
                for i in range(instruction.arg - 1, -1, -1)
            ]

            if all(instr.opcode == Opcodes.LOAD_CONST for instr in args):
                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(slice(e.arg_value for e in args))

                for arg in args:
                    arg.change_opcode(Opcodes.NOP)

                dirty = True

        elif instruction.opcode == Opcodes.BUILD_STRING:
            args = [
                mutable.trace_stack_position(instruction.offset, i)
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
        if instruction.has_jump() and not instruction.has_unconditional_jump():
            source = mutable.trace_stack_position(instruction.offset, 0)

            if source.opcode == Opcodes.LOAD_CONST:
                flag = bool(source.arg_value)

                if instruction.opcode in (
                    Opcodes.JUMP_IF_TRUE_OR_POP,
                    Opcodes.JUMP_IF_FALSE_OR_POP
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


def remove_nops(mutable: MutableFunction):
    root = mutable.instructions[0]
    root = root.optimise_tree()
    mutable.assemble_instructions_from_tree(root)