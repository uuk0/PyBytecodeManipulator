import dis
import sys
import typing

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.util import OPCODE_DATA
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
        remove_conditional_jump_from_constant_value(helper)
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
        remove_conditional_jump_from_constant_value(helper)
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


OPCODE_TO_OP: typing.Dict[int, typing.Tuple[int, typing.Callable]] = {}
OPCODE_ARG_TO_OP: typing.Dict[typing.Tuple[int, int], typing.Tuple[int, typing.Callable]] = {}
ARG_NAMES = "abcdefghi"

if sys.version_info.major == 3 and sys.version_info.minor >= 11:
    for opname, config in OPCODE_DATA.setdefault("operators", {}).items():
        opcode = getattr(Opcodes, opname)

        if isinstance(config, str):
            config: dict = {"code": config, "direct": True}

        if config.setdefault("direct", False):
            code = config["code"]
            args = config.setdefault("args", 2)

            if config.setdefault("inplace", False):
                context = {}
                exec(f"""
                def expr({', '.join(ARG_NAMES[:args])}):
                    {code}
                    return a""", context)
                expr = context["expr"]
            else:
                expr = eval(f"lambda {', '.join(ARG_NAMES[:args])}: {code}")

            OPCODE_TO_OP[opcode] = args, expr
            continue

        arg = -1

        for code in config.setdefault("binary", []):
            arg += 1

            expr = eval("lambda a, b: " + code)
            OPCODE_ARG_TO_OP[opcode, arg] = 2, expr

        for code in config.setdefault("inplace", []):
            arg += 1

            context = {}
            exec(f"""
def expr(a, b):
    {code}
    return a""", context)

            expr = context["expr"]
            OPCODE_ARG_TO_OP[opcode, arg] = 2, expr

elif sys.version_info.major > 3:
    raise RuntimeError("Someone forgot to implement this!!!")

else:
    for opname, config in OPCODE_DATA.setdefault("operators", {}).items():
        opcode = getattr(Opcodes, opname)

        if isinstance(config, str):
            config: dict = {"code": config}

        if config.setdefault("direct", True):
            code = config["code"]
            args = config.setdefault("args", 2)

            if config.setdefault("inplace", False):
                context = {}
                exec(f"""
def expr({', '.join(ARG_NAMES[:args])}):
    {code}
    return a""", context)
                expr = context["expr"]
            else:
                expr = eval(f"lambda {', '.join(ARG_NAMES[:args])}: {code}")

            OPCODE_TO_OP[opcode] = args, expr

        else:
            raise RuntimeError("Pre python 3.11 is not allowed to define arg-related operations")


def eval_constant_bytecode_expressions(helper: BytecodePatchHelper):
    for index, instr in list(helper.walk()):
        opcode = instr.opcode

        if opcode in OPCODE_TO_OP:
            args, expr = OPCODE_TO_OP[opcode]
        elif (opcode, instr.arg) in OPCODE_ARG_TO_OP:
            args, expr = OPCODE_ARG_TO_OP[opcode, instr.arg]
        else:
            continue

        args = [next(helper.findSourceOfStackIndex(index, i)) for i in range(args)]

        if all(arg.opcode == Opcodes.LOAD_CONST for arg in args):
            value = expr(*(arg.argval for arg in reversed(args)))
        else:
            continue

        for arg in args:
            helper.instruction_listing[arg.offset // 2] = create_instruction("NOP")

        helper.instruction_listing[index] = helper.patcher.createLoadConst(value)


OPCODE_DATA.setdefault("jump_data", {})
OPCODE_DATA["jump_data"].setdefault("unconditional", {})


def _parse_jump_data(data: dict) -> typing.Dict[int, typing.Callable[[typing.Any], typing.Tuple[bool, bool]]]:
    result = {}

    for opname, config in data.items():
        opcode = getattr(Opcodes, opname)

        if isinstance(config, str):
            config: dict = {"code": config}

        context = {}
        exec(f"""
def expr(value):
    state = {config['code']}

    if state:
        return True, {config.setdefault("true_pops", True)}

    return False, {config.setdefault("false_pops", True)}""", context)

        result[opcode] = context["expr"]

    return result


JUMP_ABSOLUTE = _parse_jump_data(OPCODE_DATA["jump_data"].setdefault("absolute", {}))
JUMP_FORWARDS = _parse_jump_data(OPCODE_DATA["jump_data"].setdefault("forward", {}))
JUMP_BACKWARDS = _parse_jump_data(OPCODE_DATA["jump_data"].setdefault("backward", {}))


def _opcode_or_default(name: str | None):
    return getattr(Opcodes, name) if name is not None else None


UNCONDITIONAL_JUMPS = [
    _opcode_or_default(OPCODE_DATA["jump_data"]["unconditional"].setdefault("absolute", None)),
    _opcode_or_default(OPCODE_DATA["jump_data"]["unconditional"].setdefault("forward", None)),
    _opcode_or_default(OPCODE_DATA["jump_data"]["unconditional"].setdefault("backward", None))
]


def remove_conditional_jump_from_constant_value(helper: BytecodePatchHelper):
    """
    Removes conditional jumps on constant values, left from previous optimisations

    Specs come from .json data
    """

    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1

        for index, instr in list(helper.walk())[index:]:
            opcode = instr.opcode

            if opcode in JUMP_ABSOLUTE:
                default = UNCONDITIONAL_JUMPS[0]
                expr = JUMP_ABSOLUTE[opcode]
            elif opcode in JUMP_FORWARDS:
                default = UNCONDITIONAL_JUMPS[1]
                expr = JUMP_FORWARDS[opcode]
            elif opcode in JUMP_BACKWARDS:
                default = UNCONDITIONAL_JUMPS[2]
                expr = JUMP_BACKWARDS[opcode]
            else:
                continue

            stack_top = next(helper.findSourceOfStackIndex(index, 0))

            if stack_top.opcode != Opcodes.LOAD_CONST: continue

            state, pop_top = expr(stack_top.argval)

            if state:
                helper.instruction_listing[index] = create_instruction(default, instr.arg)

                if pop_top:
                    helper.insertRegion(index, [create_instruction("POP_TOP")])
                    index += 1

            else:
                helper.instruction_listing[index] = create_instruction("POP_TOP" if pop_top else "NOP")

            break
        else:
            break
