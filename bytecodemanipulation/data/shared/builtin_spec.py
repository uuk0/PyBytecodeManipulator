import typing
import random

from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Specialization import SpecializationContainer, register
from bytecodemanipulation.MutableFunction import Instruction


ASSERT_TYPE_CASTS = False
DISCARD_ALL_ANY_WITHOUT_SIDE_EFFECT_CHECK = True


@register(typing.cast)
def specialize_typing_cast(container: SpecializationContainer):
    # typing.cast(<type>, <obj>) -> <obj>
    data_type, value = container.get_arg_specifications()

    if ASSERT_TYPE_CASTS:
        nop = Instruction(container.target, -1, Opcodes.NOP)

        bytecode = [
            value,
            Instruction(container.target, -1, Opcodes.DUP_TOP),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, isinstance),
            Instruction(container.target, -1, Opcodes.ROT_TWO),
            data_type,
            Instruction(container.target, -1, Opcodes.CALL_FUNCTION, arg=2),
            Instruction(container.target, -1, Opcodes.POP_JUMP_IF_TRUE, nop),
            Instruction(
                container.target, -1, Opcodes.LOAD_CONST, "expected data type '"
            ),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, repr),
            data_type,
            Instruction(container.target, -1, Opcodes.CALL_FUNCTION, arg=1),
            Instruction(container.target, -1, Opcodes.BINARY_ADD),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, "', but got '"),
            Instruction(container.target, -1, Opcodes.BINARY_ADD),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, repr),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, type),
            value,
            Instruction(container.target, -1, Opcodes.CALL_FUNCTION, arg=1),
            Instruction(container.target, -1, Opcodes.CALL_FUNCTION, arg=1),
            Instruction(container.target, -1, Opcodes.BINARY_ADD),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, "'"),
            Instruction(container.target, -1, Opcodes.BINARY_ADD),
            Instruction(container.target, -1, Opcodes.LOAD_CONST, ValueError),
            Instruction(container.target, -1, Opcodes.ROT_TWO),
            Instruction(container.target, -1, Opcodes.CALL_FUNCTION, arg=1),
            Instruction(container.target, -1, Opcodes.RAISE_VARARGS, arg=1),
            nop,
        ]

        container.replace_call_with_opcodes(bytecode)
        return

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
def specialize_max(container: SpecializationContainer):
    # remove when constants are mixed with no constant all but the biggest constant
    args = container.get_arg_specifications()

    if args[0].is_self:
        self = args.pop(0)
    else:
        self = None

    max_const: Instruction = None

    # todo: catch compare exceptions
    for arg in args:
        instr: Instruction = arg.get_normalized_data_instr()

        if instr and instr.has_constant():
            if max_const is None or max_const.arg_value < instr.arg_value:
                max_const = instr

    if max_const is not None:
        # todo: for non constants, do a clever try-eval-ahead with the type if arrival

        for arg in args:
            norm_instr = arg.get_normalized_data_instr()
            if norm_instr and norm_instr != max_const and norm_instr.has_constant():
                arg.discard()


@register(tuple)
def create_empty_tuple(container: SpecializationContainer):
    if len(container.get_arg_specifications()) == 0:
        container.replace_with_constant_value(tuple())


def _check_int(c) -> bool:
    if isinstance(c, int):
        return True
    if isinstance(c, float):
        return int(c) == c
    return False


@register(range)
@register(random.randrange)
@register(random.Random.randrange)
def specialize_range_3rd_argument(container: SpecializationContainer):
    args = container.get_arg_specifications()
    sources = [arg.get_normalized_data_instr() for arg in args]

    # Argument length checks and type checks
    if len(sources) in (1, 2, 3):
        if sources[0].opcode == Opcodes.LOAD_CONST:
            container.replace_with_raise_exception_if(
                not _check_int(sources[0].arg_value),
                lambda: TypeError(
                    f"'{type(sources[0].arg_value).__name__}' object cannot be interpreted as an integer"
                ),
                arg=0,
            )

        if len(sources) > 1 and sources[1].opcode == Opcodes.LOAD_CONST:
            container.replace_with_raise_exception_if(
                not _check_int(sources[1].arg_value),
                lambda: TypeError(
                    f"'{type(sources[1].arg_value).__name__}' object cannot be interpreted as an integer"
                ),
                arg=1,
            )

        if (
            len(sources) == 2
            and sources[0].opcode == sources[1].opcode == Opcodes.LOAD_CONST
            and sources[0].arg_value > sources[1].arg_value
        ):
            container.replace_with_constant_value(tuple())

        if len(sources) > 2 and sources[2].opcode == Opcodes.LOAD_CONST:
            if (
                not container.replace_with_raise_exception_if(
                    not _check_int(sources[2].arg_value),
                    lambda: TypeError(
                        f"'{type(sources[2].arg_value).__name__}' object cannot be interpreted as an integer"
                    ),
                    arg=2,
                )
                and sources[2].arg_value == 0
            ):
                container.replace_with_raise_exception(
                    lambda: ValueError("range() arg 3 must not be zero"),
                    arg=2,
                )

        if (
            len(sources) == 3
            and sources[0].opcode
            == sources[1].opcode
            == sources[2].opcode
            == Opcodes.LOAD_CONST
            and sources[0].arg_value > sources[1].arg_value
            and sources[2].arg_value > 0
        ):
            container.replace_with_constant_value(tuple())

        if (
            len(sources) == 3
            and sources[0].opcode
            == sources[1].opcode
            == sources[2].opcode
            == Opcodes.LOAD_CONST
            and sources[0].arg_value < sources[1].arg_value
            and sources[2].arg_value < 0
        ):
            container.replace_with_constant_value(tuple())

    elif len(sources) == 0:
        if container.method_call_descriptor.lookup_method_instr.arg_value == range:
            container.replace_with_raise_exception(
                TypeError("range expected at least 1 argument, got 0")
            )
        elif (
            container.method_call_descriptor.lookup_method_instr.arg_value
            == random.randrange
        ):
            container.replace_with_raise_exception(
                TypeError(
                    "Random.randrange() missing 1 required positional argument: 'start'"
                )
            )
        elif (
            container.method_call_descriptor.lookup_method_instr.arg_value
            == random.Random.randrange
        ):
            pass
        else:
            raise NotImplementedError
    else:
        if container.method_call_descriptor.lookup_method_instr.arg_value == range:
            container.replace_with_raise_exception(
                TypeError(f"range expected at most 3 arguments, got {len(sources)}")
            )
        elif (
            container.method_call_descriptor.lookup_method_instr.arg_value
            == random.randrange
        ):
            container.replace_with_raise_exception(
                TypeError(
                    f"Random.randrange() takes from 2 to 4 positional arguments but {len(sources)} were given"
                )
            )
        elif (
            container.method_call_descriptor.lookup_method_instr.arg_value
            == random.Random.randrange
        ):
            container.replace_with_raise_exception(
                TypeError(
                    f"Random.randrange() takes from 2 to 4 positional arguments but {len(sources)} were given"
                )
            )
        else:
            raise NotImplementedError

    if len(args) != 3:
        return

    if (
        args[2]
        and sources[2].opcode == Opcodes.LOAD_CONST
        and sources[2].arg_value == 1
    ):
        args[2].discard()


@register(range)
@register(random.randrange)
@register(random.Random.randrange)
def specialize_range_start_0(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) != 2:
        return

    if (
        args[0]
        and args[0].get_normalized_data_instr().opcode == Opcodes.LOAD_CONST
        and args[0].get_normalized_data_instr().arg_value == 0
    ):
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


@register(all)
def specialize_all(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) != 1:
        return

    create_primitive_arg = args[0].get_normalized_data_instr()

    if create_primitive_arg is None:
        return

    # todo: can we specialize more?
    if create_primitive_arg.opcode not in (
        Opcodes.BUILD_LIST,
        Opcodes.BUILD_TUPLE,
        Opcodes.BUILD_SET,
    ):
        return

    primitive_creation_args = [
        (
            create_primitive_arg.trace_normalized_stack_position(i),
            next(create_primitive_arg.trace_stack_position(i)),
        )
        for i in range(create_primitive_arg.arg)
    ]

    defined_result = None
    arg_count = len(primitive_creation_args)

    for normal, real in primitive_creation_args:
        if normal:
            if normal.opcode != Opcodes.LOAD_CONST:
                continue

            if not normal.arg_value:
                if DISCARD_ALL_ANY_WITHOUT_SIDE_EFFECT_CHECK:
                    defined_result = False
                    break
            else:
                real.change_opcode(Opcodes.NOP)
                arg_count -= 1

    if arg_count == 0:
        defined_result = True

    if defined_result is not None:
        for _, real in primitive_creation_args:
            real.change_opcode(Opcodes.NOP)

        create_primitive_arg.change_opcode(Opcodes.NOP)
        container.replace_with_constant_value(defined_result)
    elif arg_count == 1:
        create_primitive_arg.change_opcode(Opcodes.NOP)
        container.replace_call_with_arg(args[0])
    elif arg_count != create_primitive_arg.arg:
        create_primitive_arg.change_arg(arg_count)

        container.no_special = False


@register(any)
def specialize_any(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) != 1:
        return

    create_primitive_arg = args[0].get_normalized_data_instr()

    if create_primitive_arg is None:
        return

    # todo: can we specialize more?
    if create_primitive_arg.opcode not in (
        Opcodes.BUILD_LIST,
        Opcodes.BUILD_TUPLE,
        Opcodes.BUILD_SET,
    ):
        return

    primitive_creation_args = [
        (
            create_primitive_arg.trace_normalized_stack_position(i),
            next(create_primitive_arg.trace_stack_position(i)),
        )
        for i in range(create_primitive_arg.arg)
    ]

    defined_result = None
    arg_count = len(primitive_creation_args)

    for normal, real in primitive_creation_args:
        if normal:
            if normal.opcode != Opcodes.LOAD_CONST:
                continue

            if normal.arg_value:
                if DISCARD_ALL_ANY_WITHOUT_SIDE_EFFECT_CHECK:
                    defined_result = True
                    break
            else:
                real.change_opcode(Opcodes.NOP)
                arg_count -= 1

    if arg_count == 0:
        defined_result = False

    if defined_result is not None:
        for _, real in primitive_creation_args:
            real.change_opcode(Opcodes.NOP)

        create_primitive_arg.change_opcode(Opcodes.NOP)
        container.replace_with_constant_value(defined_result)
    elif arg_count == 1:
        create_primitive_arg.change_opcode(Opcodes.NOP)
        container.replace_call_with_arg(args[0])
    elif arg_count != create_primitive_arg.arg:
        create_primitive_arg.change_arg(arg_count)

        container.no_special = False


@register(sum)
def specialize_any(container: SpecializationContainer):
    args = container.get_arg_specifications()

    if len(args) == 1:
        if args[0].get_normalized_data_instr().opcode == Opcodes.LOAD_CONST:
            container.replace_with_constant_value(
                sum(args[0].get_normalized_data_instr().arg_value)
            )
        elif args[0].get_normalized_data_instr().opcode in (
            Opcodes.BUILD_LIST,
            Opcodes.BUILD_TUPLE,
            Opcodes.BUILD_SET,
        ):
            count = args[0].get_normalized_data_instr().arg
            args[0].get_normalized_data_instr().change_opcode(Opcodes.NOP)
            container.replace_call_with_opcodes(
                [Instruction(None, -1, Opcodes.BINARY_ADD) for _ in range(count - 1)],
                leave_args_on_stack=True,
            )
