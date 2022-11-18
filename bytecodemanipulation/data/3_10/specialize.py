import typing
import random

from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Specialization import SpecializationContainer, register
from bytecodemanipulation.MutableFunction import Instruction


ASSERT_TYPE_CASTS = False


@register(typing.cast)
def specialize_typing_cast(container: SpecializationContainer):
    # typing.cast(<type>, <obj>) -> <obj>
    data_type, value = container.get_arg_specifications()

    if ASSERT_TYPE_CASTS:
        # todo: check type
        pass

    container.replace_call_with_arg(value)


@register(min)
def specialize_min(container: SpecializationContainer):
    # remove when constants are mixed with no constant all but the smallest constant
    args = container.get_arg_specifications()

    if args[0].is_self:
        self = args.pop(0)
    else:
        self = None

    min_const: Instruction = None

    # todo: catch compare exceptions
    for arg in args:
        instr: Instruction = arg.get_normalized_data_instr()

        if instr and instr.has_constant():
            if min_const is None or min_const.arg_value > instr.arg_value:
                min_const = instr

    if min_const is not None:
        # todo: for non constants, do a clever try-eval-ahead with the type if arrival

        for arg in args:
            norm_instr = arg.get_normalized_data_instr()
            if norm_instr and norm_instr != min_const and norm_instr.has_constant():
                arg.discard()


@register(max)
def specialize_min(container: SpecializationContainer):
    # remove when constants are mixed with no constant all but the smallest constant
    args = container.get_arg_specifications()

    if args[0].is_self:
        self = args.pop(0)
    else:
        self = None

    min_const: Instruction = None

    # todo: catch compare exceptions
    for arg in args:
        instr: Instruction = arg.get_normalized_data_instr()

        if instr and instr.has_constant():
            if min_const is None or min_const.arg_value < instr.arg_value:
                min_const = instr

    if min_const is not None:
        # todo: for non constants, do a clever try-eval-ahead with the type if arrival

        for arg in args:
            norm_instr = arg.get_normalized_data_instr()
            if norm_instr and norm_instr != min_const and norm_instr.has_constant():
                arg.discard()


@register(tuple)
def create_empty_tuple(container: SpecializationContainer):
    if len(container.get_arg_specifications()) == 0:
        container.replace_with_constant_value(tuple())


@register(range)
@register(random.randrange)
@register(random.Random.randrange)
def specialize_range_3rd_argument(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) != 3: return

    if args[2] and args[2].get_normalized_data_instr().opcode == Opcodes.LOAD_CONST and args[2].get_normalized_data_instr().arg_value == 1:
        args[2].discard()


@register(range)
@register(random.randrange)
@register(random.Random.randrange)
def specialize_range_start_0(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) != 2: return

    if args[0] and args[0].get_normalized_data_instr().opcode == Opcodes.LOAD_CONST and args[0].get_normalized_data_instr().arg_value == 0:
        args[0].discard()


@register(range)
def specialize_small_range(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) == 1:
        start = 0
        instr = args[0].get_normalized_data_instr()

        if not instr or instr.opcode != Opcodes.LOAD_CONST:
            return

        end = instr.arg_value
    elif len(args) == 2:
        instr = args[0].get_normalized_data_instr()
        if not instr or instr.opcode != Opcodes.LOAD_CONST:
            return
        start = instr.arg_value

        instr = args[1].get_normalized_data_instr()
        if not instr or instr.opcode != Opcodes.LOAD_CONST:
            return
        end = instr.arg_value
    else:
        return

    if start == end:
        container.replace_with_constant_value(tuple())
    elif start + 1 == end:
        container.replace_with_constant_value((start,))
    elif start + 2 == end:
        container.replace_with_constant_value((start, start + 1))

