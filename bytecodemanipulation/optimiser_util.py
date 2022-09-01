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
}


def inline_constant_method_invokes(mutable: MutableFunction):
    repass = True

    while repass:
        repass = False

        inline_constant_binary_ops(mutable)

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

                            repass = True

    inline_constant_binary_ops(mutable)


def inline_constant_binary_ops(mutable: MutableFunction):
    for instruction in mutable.instructions:
        if instruction.opcode in OPCODE_TO_ATTR_SINGLE:
            method = OPCODE_TO_ATTR_SINGLE[instruction.opcode]

            target = mutable.trace_stack_position(instruction.offset, 0)

            if target.opcode == Opcodes.LOAD_CONST:
                value = target.arg_value

                if hasattr(value, method):
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
                        value = method()
                    except:
                        continue

                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(value)
                    target.change_opcode(Opcodes.NOP)

        elif instruction.opcode in OPCODE_TO_ATTR_DOUBLE:
            method = OPCODE_TO_ATTR_SINGLE[instruction.opcode]

            arg = mutable.trace_stack_position(instruction.offset, 0)
            target = mutable.trace_stack_position(instruction.offset, 0)

            if arg.opcode == target.opcode == Opcodes.LOAD_CONST:
                value = target.arg_value

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
                    value = method(arg.arg_value)
                except:
                    continue

                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(value)
                target.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)


def remove_nops(mutable: MutableFunction):
    root = mutable.instructions[0]
    root = root.optimise_tree()
    mutable.assemble_instructions_from_tree(root)
