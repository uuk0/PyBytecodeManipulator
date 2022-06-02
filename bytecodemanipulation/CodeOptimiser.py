import dis
import sys

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.util import Opcodes, create_instruction

SIDE_EFFECT_FREE_VALUE_LOAD = {
    Opcodes.LOAD_FAST,
    Opcodes.LOAD_GLOBAL,
    Opcodes.LOAD_CONST,
    Opcodes.LOAD_DEREF,
    Opcodes.LOAD_CLASSDEREF,
    Opcodes.LOAD_NAME,
    Opcodes.LOAD_ASSERTION_ERROR,
    Opcodes.LOAD_BUILD_CLASS,
    Opcodes.LOAD_CLOSURE,
    Opcodes.LOAD_METHOD,
}

# These build primitives from A objects from the stack
BUILD_PRIMITIVE = {
    Opcodes.BUILD_TUPLE,
    Opcodes.BUILD_SET,
    Opcodes.BUILD_LIST,
}


PAIR_LOAD_STORE = {
    Opcodes.LOAD_FAST: Opcodes.STORE_FAST,
    Opcodes.LOAD_GLOBAL: Opcodes.STORE_GLOBAL,
    Opcodes.LOAD_NAME: Opcodes.STORE_NAME,
    Opcodes.LOAD_DEREF: Opcodes.STORE_DEREF,
}
PAIR_STORE_LOAD = {value: key for key, value in PAIR_LOAD_STORE.items()}

PAIR_LOAD_STORE_SIDE_FREE = {
    Opcodes.LOAD_FAST: Opcodes.STORE_FAST,
    Opcodes.LOAD_GLOBAL: Opcodes.STORE_GLOBAL,
}
PAIR_STORE_LOAD_SIDE_FREE = {value: key for key, value in PAIR_LOAD_STORE_SIDE_FREE.items()}

PAIR_STORE_DELETE = {
    Opcodes.STORE_FAST: Opcodes.DELETE_FAST,
    Opcodes.STORE_NAME: Opcodes.DELETE_NAME,
    Opcodes.STORE_GLOBAL: Opcodes.DELETE_GLOBAL,
    Opcodes.STORE_DEREF: Opcodes.DELETE_DEREF,
}


if sys.version_info.major <= 3 and sys.version_info.minor < 11:
    def optimise_code(helper: BytecodePatchHelper):
        remove_store_delete_pairs(helper)
        remove_load_dup_pop(helper)
        remove_load_store_pairs(helper)
        optimise_store_load_pairs(helper)
        remove_delete_fast_without_assign(helper)
        remove_store_fast_without_usage(helper)
        # trace_load_const_store_fast_load_fast(helper)
        remove_nop(helper)
        eval_constant_bytecode_expressions(helper)
        prepare_inline_expressions(helper)
        remove_create_primitive_pop(helper)
        remove_load_dup_pop(helper)
        remove_delete_fast_without_assign(helper)
        remove_load_dup_pop(helper)

else:
    # todo: stack manipulation methods changed

    def optimise_code(helper: BytecodePatchHelper):
        remove_store_delete_pairs(helper)
        remove_load_dup_pop(helper)
        remove_load_store_pairs(helper)
        optimise_store_load_pairs(helper)
        remove_delete_fast_without_assign(helper)
        remove_store_fast_without_usage(helper)
        # trace_load_const_store_fast_load_fast(helper)
        remove_nop(helper)
        eval_constant_bytecode_expressions(helper)
        prepare_inline_expressions(helper)
        remove_create_primitive_pop(helper)
        remove_load_dup_pop(helper)
        remove_delete_fast_without_assign(helper)
        remove_load_dup_pop(helper)


# Optimise-able:
# constant + conditional jump -> unconditional jump / no code
# empty for_iter
# RAISE in a try-except block ignoring the exception or handling only the exception instance
# CALL_FUNCTION to a side effect free method followed by a POP_TOP
# CALL_FUNCTION_KW to a side effect free method followed by a POP_TOP
# MAKE_FUNCTION directly popped from the stack
# is_constant() marker for function calls, together with local type hints
# side effect free popped math operation (Value check / value type hint)
# Single/more-accessed STORE_XX in a following region which can be served via the stack

# todo: track LOAD_XX better, depending on context, we may have some other instructions in between,
#   but we can optimise these instructions away


def remove_store_delete_pairs(helper: BytecodePatchHelper):
    """
    Optimiser method for removing side effect free STORE_XX instructions directly followed by a
    DELETE_XX instruction.
    Refactors it into a POP_TOP followed by a DELETE_XX

    The POP_TOP instruction than can be optimised away by the remove_load_dup_pop() optimiser if possible.
    The DELETE_XX instruction can be optimised away by the remove_delete_fast_without_assign() optimiser if possible.
    """
    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if (
                instr.opcode in PAIR_STORE_DELETE
                and index < len(helper.instruction_listing) - 2
            ):
                next_instr = helper.instruction_listing[index + 1]
                if (
                    next_instr.opcode == PAIR_STORE_DELETE[instr.opcode]
                    and instr.arg == next_instr.arg
                ):
                    # Delete the load instruction and the store instruction
                    helper.instruction_listing[index] = dis.Instruction(
                        "POP_TOP",
                        Opcodes.POP_TOP,
                        0,
                        0,
                        "",
                        0,
                        0,
                        False,
                    )
                    break
        else:
            break


def remove_delete_fast_without_assign(helper: BytecodePatchHelper):
    """
    Removes all DELETE_FAST instructions deleting locals not written to yet
    This is an artifact left by other optimisation functions
    """
    # the arguments are written to, but anything else is not
    written_to = set(range(helper.patcher.argument_count))

    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if instr.opcode == Opcodes.STORE_FAST:
                written_to.add(instr.arg)

            elif instr.opcode == Opcodes.DELETE_FAST and instr.arg not in written_to:
                helper.deleteRegion(index, index + 1)
                index -= 1
                break
        else:
            break


def remove_load_dup_pop(helper: BytecodePatchHelper):
    """
    Optimiser method for removing side effect free LOAD_XX and DUP_TOP instructions directly followed by a
    POP_TOP instruction
    """
    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if instr.opcode == Opcodes.POP_TOP and index > 0:
                previous = helper.instruction_listing[index - 1]
                if previous.opcode in SIDE_EFFECT_FREE_VALUE_LOAD or previous.opcode == Opcodes.DUP_TOP:
                    # Delete the side effect free result and the POP_TOP instruction
                    helper.deleteRegion(index - 1, index + 1)
                    index -= 2
                    break
        else:
            break


def remove_load_store_pairs(helper: BytecodePatchHelper):
    """
    Optimiser method for removing side effect free LOAD_XX followed by STORE_XX to the same space

    Removing e.g. a = a in the process
    """

    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if (
                instr.opcode in PAIR_LOAD_STORE
                and index < len(helper.instruction_listing) - 2
            ):
                next_instr = helper.instruction_listing[index + 1]
                if (
                    next_instr.opcode == PAIR_LOAD_STORE[instr.opcode]
                    and instr.arg == next_instr.arg
                ):
                    # Delete the load instruction and the store instruction
                    helper.deleteRegion(index, index + 2)
                    index -= 1
                    break
        else:
            break


def optimise_store_load_pairs(helper: BytecodePatchHelper):
    """
    Optimiser method for removing a side effect free STORE_XX followed by a LOAD_XX
    to a DUP followed by the STORE_XX instruction
    """

    for index, instr in list(helper.walk()):
        if (
            instr.opcode in PAIR_STORE_LOAD_SIDE_FREE
            and index < len(helper.instruction_listing) - 2
        ):
            next_instr = helper.instruction_listing[index + 1]
            if (
                next_instr.opcode == PAIR_STORE_LOAD_SIDE_FREE[instr.opcode]
                and instr.arg == next_instr.arg
            ):
                helper.instruction_listing[index + 1] = instr
                helper.instruction_listing[index] = create_instruction("DUP_TOP")


def remove_store_fast_without_usage(helper: BytecodePatchHelper):
    """
    Optimisation for removing STORE_FAST instructions writing to locals not used later on
    """

    last_reads = [-1] * len(helper.patcher.variable_names)

    for index, instr in list(helper.walk()):
        if (
            instr.opcode == Opcodes.LOAD_FAST
        ):
            last_reads[instr.arg] = index

    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            # Ok, the STORE_FAST is after the last LOAD_FAST instruction, so we can replace eit by a POP_TOP
            if instr.opcode == Opcodes.STORE_FAST and index > last_reads[instr.arg]:
                helper.instruction_listing[index] = create_instruction("POP_TOP")


def remove_create_primitive_pop(helper: BytecodePatchHelper):
    index = 0
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if instr.opcode == Opcodes.POP_TOP and index > 0:
                previous = helper.instruction_listing[index - 1]
                if previous.opcode in BUILD_PRIMITIVE:
                    helper.deleteRegion(index - 1, index + 1)
                    helper.insertRegion(index - 1, [create_instruction("POP_TOP")] * previous.arg)
                elif previous.opcode == Opcodes.BUILD_MAP:
                    # BUILD_MAP requires twice the values
                    helper.deleteRegion(index - 1, index + 1)
                    helper.insertRegion(index - 1, [create_instruction("POP_TOP")] * (previous.arg * 2))


def remove_nop(helper: BytecodePatchHelper):
    """
    Optimiser method for removing NOP instructions
    todo: can we combine-delete multiple instructions?
    """

    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if instr.opcode == Opcodes.NOP:
                helper.deleteRegion(index, index + 1, maps_invalid_to=index)
                index -= 1
                break
        else:
            break


def prepare_inline_expressions(helper: BytecodePatchHelper):
    """
    Optimiser for optimising constant expressions in bytecode

    Currently, only optimises tuple building of constants, which is already optimised by the compiler;
    So this is only useful when cleaning up other optimised sections
    """

    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1

        for index, instr in list(helper.walk())[index:]:
            if instr.opcode == Opcodes.BUILD_TUPLE:
                count = instr.arg

                args = []
                for i in range(count):
                    value = next(helper.findTargetOfStackIndex(i, index))

                    if value.opcode == Opcodes.LOAD_CONST:
                        args.append(value.argval)
                    else:
                        break

                else:
                    helper.instruction_listing[index] = helper.patcher.createLoadConst(tuple(args))
                    helper.insertRegion(index, [create_instruction("POP_TOP")] * len(args))

            # todo: for lists/sets/dicts, check usage for constant use (check for "in", lookup, ...)


def trace_load_const_store_fast_load_fast(helper: BytecodePatchHelper):
    """
    Traces the following bytecode layouts:

    LOAD_CONST XY
    ...
    STORE_FAST XY -> AB
    ...
    LOAD_FAST AB
    ...

    where the last LOAD_FAST AB becomes a LOAD_CONST XY

    Currently, not in use, as I did not find a case where this optimising is not applied by another function
    """

    known_var_values = {}

    for index, instr in list(helper.walk()):
        if instr.opcode == Opcodes.STORE_FAST:
            value_instr = next(helper.findSourceOfStackIndex(index, 0))

            if value_instr.opcode == Opcodes.LOAD_CONST:
                known_var_values[instr.arg] = value_instr.argval
            elif instr.arg in known_var_values:
                del known_var_values[instr.arg]

        elif instr.opcode == Opcodes.LOAD_FAST:
            if instr.arg in known_var_values:
                helper.instruction_listing[index] = helper.patcher.createLoadConst(known_var_values[instr.arg])


TAKES_ONE = {
    Opcodes.UNARY_POSITIVE,
    Opcodes.UNARY_NEGATIVE,
    Opcodes.UNARY_NOT,
    Opcodes.UNARY_INVERT,
    Opcodes.LIST_TO_TUPLE,
}
TAKES_TWO = {
    Opcodes.BINARY_MATRIX_MULTIPLY,
    Opcodes.INPLACE_MATRIX_MULTIPLY,
    Opcodes.BINARY_POWER,
    Opcodes.BINARY_MULTIPLY,
    Opcodes.BINARY_MODULO,
    Opcodes.BINARY_ADD,
    Opcodes.BINARY_SUBTRACT,
    Opcodes.BINARY_SUBSCR,
    Opcodes.BINARY_FLOOR_DIVIDE,
    Opcodes.BINARY_TRUE_DIVIDE,
    Opcodes.INPLACE_FLOOR_DIVIDE,
    Opcodes.INPLACE_TRUE_DIVIDE,
    Opcodes.INPLACE_ADD,
    Opcodes.INPLACE_SUBTRACT,
    Opcodes.INPLACE_MULTIPLY,
    Opcodes.INPLACE_MODULO,
    Opcodes.BINARY_LSHIFT,
    Opcodes.BINARY_RSHIFT,
    Opcodes.BINARY_AND,
    Opcodes.BINARY_XOR,
    Opcodes.BINARY_OR,
    Opcodes.INPLACE_POWER,
    Opcodes.INPLACE_LSHIFT,
    Opcodes.INPLACE_RSHIFT,
    Opcodes.INPLACE_AND,
    Opcodes.INPLACE_XOR,
    Opcodes.INPLACE_OR,
}


def eval_constant_bytecode_expressions(helper: BytecodePatchHelper):
    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1

        for index, instr in list(helper.walk())[index:]:
            opcode = instr.opcode

            if opcode in TAKES_ONE:
                arg_instr = next(helper.findSourceOfStackIndex(index, 0))

                if arg_instr.opcode != Opcodes.LOAD_CONST: continue

                value = arg_instr.argval

                if opcode == Opcodes.UNARY_POSITIVE:
                    value = +value
                elif opcode == Opcodes.UNARY_NEGATIVE:
                    value = -value
                elif opcode == Opcodes.UNARY_NOT:
                    value = not value
                elif opcode == Opcodes.UNARY_INVERT:
                    value = ~value
                elif opcode == Opcodes.LIST_TO_TUPLE:
                    value = tuple(value)
                else:
                    raise RuntimeError(opcode)

                helper.instruction_listing[arg_instr.offset // 2] = create_instruction("NOP")

            elif opcode in TAKES_TWO:
                lhs_instr = next(helper.findSourceOfStackIndex(index, 0))
                rhs_instr = next(helper.findSourceOfStackIndex(index, 1))

                if not (rhs_instr.opcode == lhs_instr.opcode == Opcodes.LOAD_CONST):
                    continue

                rhs = rhs_instr.argval
                lhs = lhs_instr.argval

                # TODO: we need something better here!!!
                if opcode == Opcodes.BINARY_MATRIX_MULTIPLY:
                    value = rhs @ lhs
                elif opcode == Opcodes.INPLACE_MATRIX_MULTIPLY:
                    rhs @= lhs
                    value = rhs
                elif opcode == Opcodes.BINARY_POWER:
                    value = rhs ** lhs
                elif opcode == Opcodes.BINARY_MULTIPLY:
                    value = rhs * lhs
                elif opcode == Opcodes.BINARY_MODULO:
                    value = rhs % lhs
                elif opcode == Opcodes.BINARY_ADD:
                    value = rhs + lhs
                elif opcode == Opcodes.BINARY_SUBTRACT:
                    value = rhs - lhs
                elif opcode == Opcodes.BINARY_SUBSCR:
                    value = rhs[lhs]
                elif opcode == Opcodes.BINARY_FLOOR_DIVIDE:
                    value = rhs // lhs
                elif opcode == Opcodes.BINARY_TRUE_DIVIDE:
                    value = rhs / lhs
                elif opcode == Opcodes.INPLACE_FLOOR_DIVIDE:
                    rhs //= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_TRUE_DIVIDE:
                    rhs /= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_ADD:
                    rhs += lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_SUBTRACT:
                    rhs -= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_MULTIPLY:
                    rhs *= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_MODULO:
                    rhs %= lhs
                    value = rhs
                elif opcode == Opcodes.BINARY_LSHIFT:
                    value = rhs << lhs
                elif opcode == Opcodes.BINARY_RSHIFT:
                    value = rhs >> lhs
                elif opcode == Opcodes.BINARY_AND:
                    value = rhs & lhs
                elif opcode == Opcodes.BINARY_XOR:
                    value = rhs ^ lhs
                elif opcode == Opcodes.BINARY_OR:
                    value = rhs | lhs
                elif opcode == Opcodes.INPLACE_POWER:
                    rhs **= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_LSHIFT:
                    rhs <<= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_RSHIFT:
                    rhs >>= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_AND:
                    rhs &= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_XOR:
                    rhs ^= lhs
                    value = rhs
                elif opcode == Opcodes.INPLACE_OR:
                    rhs |= lhs
                    value = rhs
                else:
                    raise RuntimeError(opcode)

                helper.instruction_listing[rhs_instr.offset // 2] = create_instruction("NOP")
                helper.instruction_listing[lhs_instr.offset // 2] = create_instruction("NOP")

            else:
                continue

            helper.instruction_listing[index] = helper.patcher.createLoadConst(value)
