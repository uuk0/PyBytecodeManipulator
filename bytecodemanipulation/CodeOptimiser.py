import dis

from bytecodemanipulation.TransformationHelper import MixinPatchHelper
from bytecodemanipulation.util import Opcodes

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


PAIR_LOAD_STORE = {
    Opcodes.LOAD_FAST: Opcodes.STORE_FAST,
    Opcodes.LOAD_GLOBAL: Opcodes.STORE_GLOBAL,
    Opcodes.LOAD_NAME: Opcodes.STORE_NAME,
    Opcodes.LOAD_DEREF: Opcodes.STORE_DEREF,
}

PAIR_STORE_DELETE = {
    Opcodes.STORE_FAST: Opcodes.DELETE_FAST,
    Opcodes.STORE_NAME: Opcodes.DELETE_NAME,
    Opcodes.STORE_GLOBAL: Opcodes.DELETE_GLOBAL,
    Opcodes.STORE_DEREF: Opcodes.DELETE_DEREF,
}


def optimise_code(helper: MixinPatchHelper):
    remove_store_delete_pairs(helper)
    remove_load_pop(helper)
    remove_load_store_pairs(helper)
    remove_delete_fast_without_assign(helper)
    remove_nop(helper)


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


def remove_store_delete_pairs(helper: MixinPatchHelper):
    """
    Optimiser method for removing side effect free STORE_XX instructions directly followed by a
    DELETE_XX instruction.
    Refactors it into a POP_TOP followed by a DELETE_XX

    The POP_TOP instruction than can be optimised away by the remove_load_pop() optimiser if possible.
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


def remove_delete_fast_without_assign(helper: MixinPatchHelper):
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


def remove_load_pop(helper: MixinPatchHelper):
    """
    Optimiser method for removing side effect free LOAD_XX instructions directly followed by a
    POP_TOP instruction
    """
    index = -1
    while index < len(helper.instruction_listing) - 1:
        index += 1
        for index, instr in list(helper.walk())[index:]:
            if instr.opcode == Opcodes.POP_TOP and index > 0:
                previous = helper.instruction_listing[index - 1]
                if previous.opcode in SIDE_EFFECT_FREE_VALUE_LOAD:
                    # Delete the side effect free result and the POP_TOP instruction
                    helper.deleteRegion(index - 1, index + 1)
                    index -= 2
                    break
        else:
            break


def remove_load_store_pairs(helper: MixinPatchHelper):
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


def remove_nop(helper: MixinPatchHelper):
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
