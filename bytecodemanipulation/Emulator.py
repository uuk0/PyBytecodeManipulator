import builtins
import importlib
import string
import typing
from inspect import CO_GENERATOR

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


class UnknownOpcodeError(Exception):
    pass


class FinalReturn(Exception):
    pass


class YieldValue(Exception):
    pass


class StackSizeIssue(Exception):
    pass


class EmulatorGeneratorContainer:
    def __init__(self, mutable: MutableFunction, args: typing.Sized = tuple()):
        self.mutable = mutable
        self.instruction = mutable.instructions[0]
        self.args = args

        if len(self.args) != self.mutable.argument_count:
            raise ValueError()

        self.stack = []
        self.local_variables = [None] * len(self.mutable.shared_variable_names)
        self.local_variables[: len(self.args)] = self.args
        self.free_vars = [None] * len(mutable.free_variables)
        self.exception_handle_stack = []

        self.instruction = self.mutable.instructions[0]
        self.continue_stack = []

        if not isinstance(self.mutable, MutableFunction):
            self.mutable = MutableFunction(self.mutable)

    def run(self):
        print("yield-calling", self.mutable)

        while True:
            # print("run", self.instruction)
            # print(self.stack)
            # print(self.local_variables)
            target = OPCODE_FUNCS[self.instruction.opcode]

            if target is None:
                raise UnknownOpcodeError(self.instruction)

            try:
                self.instruction, self.mutable = target(
                    self.mutable,
                    self.instruction,
                    self.stack,
                    self.local_variables,
                    self.free_vars,
                    self.continue_stack,
                    self.exception_handle_stack,
                )
            except FinalReturn as e:
                raise StopIteration
            except YieldValue as e:
                if len(e.args) > 1:
                    self.instruction, self.mutable = e.args[1:]

                return e.args[0]

    def __iter__(self):
        return self

    def __next__(self):
        return self.run()


def run_code(mutable: MutableFunction | typing.Callable, *args):
    print("calling", mutable)

    if not isinstance(mutable, MutableFunction):
        mutable = MutableFunction(mutable)

    mutable: MutableFunction

    if len(args) != mutable.argument_count:
        raise ValueError()

    stack = []
    local_variables = [None] * len(mutable.shared_variable_names)
    local_variables[: len(args)] = args
    free_vars = [None] * len(mutable.free_variables)
    exception_handle_stack = []

    instruction = mutable.instructions[0]
    continue_stack = []

    while True:
        print(instruction)
        print(stack)
        target = OPCODE_FUNCS[instruction.opcode]

        if target is None:
            raise UnknownOpcodeError(instruction)

        try:
            instruction, mutable = target(
                mutable,
                instruction,
                stack,
                local_variables,
                free_vars,
                continue_stack,
                exception_handle_stack,
            )
        except FinalReturn as e:
            if len(e.args) > 1:
                instruction, mutable = e.args[1:]

            return e.args[0]
        except YieldValue:
            raise RuntimeError("YIELD outside GENERATOR")

        if len(stack) > mutable.stack_size:
            raise StackSizeIssue(f"{len(stack)} > {mutable.stack_size}")


OPCODE_FUNCS: typing.List[typing.Callable | None] = [None] * 256


def execution(opcode: int):
    def target(
        func: typing.Callable[
            [MutableFunction, Instruction, list, list, list, list, list],
            typing.Tuple[Instruction, MutableFunction],
        ]
    ):
        OPCODE_FUNCS[opcode] = func
        return func

    return target


@execution(Opcodes.NOP)
@execution(Opcodes.GEN_START)
def nop(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    return instr.next_instruction, func


@execution(Opcodes.POP_TOP)
def pop_top(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.JUMP_ABSOLUTE)
@execution(Opcodes.JUMP_FORWARD)
def jump_unconditional(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    return instr.arg_value, func


@execution(Opcodes.LOAD_GLOBAL)
def load_global(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    try:
        stack.append(func.target.__globals__[instr.arg_value])
    except KeyError:
        stack.append(getattr(builtins, instr.arg_value))

    return instr.next_instruction, func


@execution(Opcodes.STORE_GLOBAL)
def store_global(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    func.target.__globals__[instr.arg_value] = stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.LOAD_METHOD)
@execution(Opcodes.LOAD_ATTR)
def load_attr(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    obj = stack.pop(-1)
    try:
        stack.append(getattr(obj, instr.arg_value))
    except AttributeError:
        print(obj, instr)
        raise

    return instr.next_instruction, func


@execution(Opcodes.STORE_ATTR)
def load_attr(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    setattr(stack.pop(-1), instr.arg_value, stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.LOAD_FAST)
def load_fast(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(local[instr.arg])
    return instr.next_instruction, func


@execution(Opcodes.STORE_FAST)
def store_fast(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    local[instr.arg] = stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.LOAD_CONST)
def load_const(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(instr.arg_value)
    return instr.next_instruction, func


@execution(Opcodes.LOAD_DEREF)
@execution(Opcodes.LOAD_CLOSURE)
def load_deref(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(free_vars[instr.arg])
    return instr.next_instruction, func


@execution(Opcodes.STORE_DEREF)
def store_deref(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    free_vars += [None] * (instr.arg + 1 - len(free_vars))
    free_vars[instr.arg] = stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.CALL_METHOD)
@execution(Opcodes.CALL_FUNCTION)
def call_method(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    args = list(reversed([stack.pop(-1) for _ in range(instr.arg)]))
    target = stack.pop(-1)

    if hasattr(target, "__self__") and hasattr(target, "__code__"):
        args.insert(0, target.__self__)

    try:
        mutable = MutableFunction(target)
    except AttributeError:
        stack.append(target(*args))
        return instr.next_instruction, func

    if mutable.code_flags & CO_GENERATOR:
        stack.append(EmulatorGeneratorContainer(mutable, args))
        return instr.next_instruction, func

    call_stack.append(
        (
            func,
            stack[:],
            local[:],
            instr.next_instruction,
            exception_handle_stack[:],
            free_vars[:],
        )
    )

    free_vars.clear()

    free_vars[:] = [None] * len(mutable.free_variables)

    if hasattr(target, "_CELL_SPACE"):
        free_vars[: len(target._CELL_SPACE)] = target._CELL_SPACE

    stack.clear()
    local[:] = [None] * len(mutable.shared_variable_names)
    local[: len(args)] = args

    print("calling", mutable)

    return mutable.instructions[0], mutable


@execution(Opcodes.RETURN_VALUE)
def return_value(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    return_obj = stack.pop(-1)

    print("returning", func)
    print(return_obj)

    if len(call_stack) == 0:
        raise FinalReturn(return_obj)

    (
        func,
        stack[:],
        local[:],
        next_instr,
        exception_handle_stack[:],
        free_vars[:],
    ) = call_stack.pop(-1)

    stack.append(return_obj)

    return next_instr, func


@execution(Opcodes.YIELD_VALUE)
def yield_value(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
):
    value = stack.pop(-1)
    stack.append(None)
    raise YieldValue(value, instr.next_instruction, func)


@execution(Opcodes.YIELD_FROM)
def yield_from(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    null = stack.pop(-1)

    if null is not None:
        raise RuntimeError("expected None, got " + repr(null))

    tos = stack[-1]

    try:
        raise YieldValue(next(tos))
    except StopIteration:
        stack.pop(-1)
        stack.append(None)
        return instr.next_instruction, func


@execution(Opcodes.POP_JUMP_IF_TRUE)
def pop_jump_if_true(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    case = stack.pop(-1)

    if case:
        return instr.arg_value, func
    return instr.next_instruction, func


@execution(Opcodes.JUMP_IF_TRUE_OR_POP)
def jump_if_true_or_pop(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    case = stack[-1]

    if case:
        return instr.arg_value, func

    stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.POP_JUMP_IF_FALSE)
def pop_jump_if_false(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    case = stack.pop(-1)

    if not case:
        return instr.arg_value, func
    return instr.next_instruction, func


@execution(Opcodes.CONTAINS_OP)
def contains_op(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    state = stack.pop(-2) in stack.pop(-1)

    if instr.arg:
        state = not state

    stack.append(state)

    return instr.next_instruction, func


@execution(Opcodes.IS_OP)
def is_op(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    state = stack.pop(-2) is stack.pop(-1)

    if instr.arg:
        state = not state

    stack.append(state)

    return instr.next_instruction, func


@execution(Opcodes.COMPARE_OP)
def compare_op(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    op = ("<", "<=", "==", "!=", ">", ">=")[instr.arg]
    a, b = stack.pop(-2), stack.pop(-1)

    stack.append(eval(f"a {op} b", {"a": a, "b": b}))

    return instr.next_instruction, func


@execution(Opcodes.BINARY_SUBSCR)
def binary_subscr(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2)[stack.pop(-1)])

    return instr.next_instruction, func


@execution(Opcodes.BINARY_ADD)
def binary_add(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2) + stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.INPLACE_ADD)
def binary_subtract(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    a, b = stack.pop(-2), stack.pop(-1)
    a += b
    stack.append(a)

    return instr.next_instruction, func


@execution(Opcodes.BINARY_SUBTRACT)
def binary_subtract(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2) - stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.INPLACE_SUBTRACT)
def binary_subtract(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    a, b = stack.pop(-2), stack.pop(-1)
    a -= b
    stack.append(a)

    return instr.next_instruction, func


@execution(Opcodes.BINARY_MULTIPLY)
def binary_subtract(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2) * stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.INPLACE_MULTIPLY)
def binary_subtract(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    a, b = stack.pop(-2), stack.pop(-1)
    a *= b
    stack.append(a)

    return instr.next_instruction, func


@execution(Opcodes.SETUP_FINALLY)
def setup_finally(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    exception_handle_stack.append(instr.arg_value)
    return instr.next_instruction, func


@execution(Opcodes.POP_BLOCK)
def pop_block(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    exception_handle_stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.IMPORT_NAME)
def import_name(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(importlib.import_module(instr.arg_value))
    return instr.next_instruction, func


@execution(Opcodes.IMPORT_FROM)
def import_name(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(getattr(stack.pop(-1), instr.arg_value))
    return instr.next_instruction, func


@execution(Opcodes.GET_ITER)
@execution(Opcodes.GET_YIELD_FROM_ITER)
def get_iter(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(iter(stack.pop(-1)))
    return instr.next_instruction, func


@execution(Opcodes.FOR_ITER)
def for_iter(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:

    iterator = stack[-1]

    try:
        stack.append(next(iterator))
    except StopIteration:
        stack.pop(-1)
        return typing.cast(Instruction, instr.arg_value), func

    return instr.next_instruction, func


@execution(Opcodes.BUILD_TUPLE)
def build_tuple(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(tuple(reversed([stack.pop(-1) for _ in range(instr.arg)])))
    return instr.next_instruction, func


@execution(Opcodes.BUILD_LIST)
def build_tuple(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(list(reversed([stack.pop(-1) for _ in range(instr.arg)])))
    return instr.next_instruction, func


@execution(Opcodes.BUILD_SET)
def build_set(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(set([stack.pop(-1) for _ in range(instr.arg)]))
    return instr.next_instruction, func


@execution(Opcodes.UNPACK_SEQUENCE)
def unpack_sequence(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    stack += reversed(stack.pop(-1))
    return instr.next_instruction, func


@execution(Opcodes.LIST_EXTEND)
def list_extend(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    l = stack[-instr.arg - 1]
    obj = stack.pop(-1)
    l.extend(obj)
    return instr.next_instruction, func


@execution(Opcodes.MAKE_FUNCTION)
def make_function(
    func: MutableFunction,
    instr: Instruction,
    stack: list,
    local: list,
    free_vars: list,
    call_stack: list,
    exception_handle_stack: list,
) -> typing.Tuple[Instruction, MutableFunction]:
    flags = instr.arg

    add_args = []
    add_kwargs = {}
    parameter_annotations = []
    cells = []

    qualified_name = stack.pop(-1)
    code_obj = stack.pop(-1)

    if flags & 0x08:  # free var cells
        cells += stack.pop(-1)

    if flags & 0x04:  # parameter annotations
        parameter_annotations += stack.pop(-1)

    if flags & 0x02:  # keyword-args
        add_kwargs.update(stack.pop(-1))

    if flags & 0x01:  # default arg tuple
        add_args += stack.pop(-1)

    cell_names = string.ascii_lowercase[: len(cells)]

    if cell_names:
        create = f"""

def init():
    {', '.join(cell_names)} = {", ".join(["None"] * len(cell_names))}
    
    def target():
        {', '.join(cell_names)}
    
    return target
"""

        space = {}
        exec(create, space)
        target = space["init"]()
    else:

        def target():
            pass

    target._CELL_SPACE = cells[:]

    target.__code__ = code_obj
    target.__name__ = qualified_name

    stack.append(
        lambda *args, **kwargs: target(*add_args, *args, **add_kwargs, **kwargs)
    )

    return instr.next_instruction, func
