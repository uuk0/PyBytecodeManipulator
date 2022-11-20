import builtins
import importlib
import typing

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


class UnknownOpcodeError(Exception): pass
class FinalReturn(Exception): pass


def run_code(mutable: MutableFunction | typing.Callable, *args):
    print("calling", mutable)

    if not isinstance(mutable, MutableFunction):
        mutable = MutableFunction(mutable)

    if len(args) != mutable.argument_count:
        raise ValueError()

    stack = []
    local_variables = [None] * len(mutable.shared_variable_names)
    local_variables[:len(args)] = args
    exception_handle_stack = []

    instruction = mutable.instructions[0]
    continue_stack = []

    while True:
        # print(instruction)
        target = OPCODE_FUNCS[instruction.opcode]

        if target is None:
            raise UnknownOpcodeError(instruction)

        try:
            instruction, mutable = target(mutable, instruction, stack, local_variables, continue_stack, exception_handle_stack)
        except FinalReturn as e:
            return e.args[0]


OPCODE_FUNCS: typing.List[typing.Callable | None] = [None] * 256


def execution(opcode: int):
    def target(func: typing.Callable[[MutableFunction, Instruction, list, list, list, list], typing.Tuple[Instruction, MutableFunction]]):
        OPCODE_FUNCS[opcode] = func
        return func

    return target


@execution(Opcodes.NOP)
def nop(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    return instr.next_instruction, func


@execution(Opcodes.POP_TOP)
def pop_top(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.JUMP_ABSOLUTE)
@execution(Opcodes.JUMP_FORWARD)
def nop(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    return instr.arg_value, func


@execution(Opcodes.LOAD_GLOBAL)
def load_global(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    try:
        stack.append(func.target.__globals__[instr.arg_value])
    except KeyError:
        stack.append(getattr(builtins, instr.arg_value))

    return instr.next_instruction, func


@execution(Opcodes.LOAD_METHOD)
@execution(Opcodes.LOAD_ATTR)
def load_attr(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    obj = stack.pop(-1)
    try:
        stack.append(getattr(obj, instr.arg_value))
    except AttributeError:
        print(obj, instr)
        raise

    return instr.next_instruction, func


@execution(Opcodes.STORE_ATTR)
def load_attr(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    setattr(stack.pop(-1), instr.arg_value, stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.LOAD_FAST)
def load_fast(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(local[instr.arg])
    return instr.next_instruction, func


@execution(Opcodes.STORE_FAST)
def store_fast(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    local[instr.arg] = stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.LOAD_CONST)
def load_const(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(instr.arg_value)
    return instr.next_instruction, func


@execution(Opcodes.CALL_METHOD)
@execution(Opcodes.CALL_FUNCTION)
def call_method_instr(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    args = list(reversed([stack.pop(-1) for _ in range(instr.arg)]))
    target = stack.pop(-1)

    if hasattr(target, "__self__") and hasattr(target, "__code__"):
        args.insert(0, target.__self__)

    try:
        mutable = MutableFunction(target)
    except AttributeError:
        stack.append(target(*args))
        return instr.next_instruction, func

    call_stack.append((func, stack[:], local[:], instr.next_instruction, exception_handle_stack))

    stack.clear()
    local[:] = [None] * len(mutable.shared_variable_names)
    local[:len(args)] = args

    print("calling", mutable)

    return mutable.instructions[0], mutable


@execution(Opcodes.RETURN_VALUE)
def return_value(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    return_obj = stack.pop(-1)

    print("returning", func)
    print(return_obj)

    func, stack[:], local[:], next_instr, exception_handle_stack[:] = call_stack.pop(-1)

    stack.append(return_obj)

    return next_instr, func


@execution(Opcodes.POP_JUMP_IF_TRUE)
def pop_jump_if_true(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    case = stack.pop(-1)

    if case:
        return instr.arg_value, func
    return instr.next_instruction, func


@execution(Opcodes.JUMP_IF_TRUE_OR_POP)
def jump_if_true_or_pop(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    case = stack[-1]

    if case:
        return instr.arg_value, func

    stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.POP_JUMP_IF_FALSE)
def pop_jump_if_false(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    case = stack.pop(-1)

    if not case:
        return instr.arg_value, func
    return instr.next_instruction, func


@execution(Opcodes.CONTAINS_OP)
def contains_op(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    state = stack.pop(-2) in stack.pop(-1)

    if instr.arg:
        state = not state

    stack.append(state)

    return instr.next_instruction, func


@execution(Opcodes.IS_OP)
def is_op(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    state = stack.pop(-2) is stack.pop(-1)

    if instr.arg:
        state = not state

    stack.append(state)

    return instr.next_instruction, func


@execution(Opcodes.COMPARE_OP)
def compare_op(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    op = ('<', '<=', '==', '!=', '>', '>=')[instr.arg]
    a, b = stack.pop(-2), stack.pop(-1)

    stack.append(eval(f"a {op} b", {"a": a, "b": b}))

    return instr.next_instruction, func


@execution(Opcodes.BINARY_SUBSCR)
def binary_subscr(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2)[stack.pop(-1)])

    return instr.next_instruction, func


@execution(Opcodes.BINARY_ADD)
def binary_add(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2) + stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.BINARY_SUBTRACT)
def binary_subtract(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(stack.pop(-2) - stack.pop(-1))

    return instr.next_instruction, func


@execution(Opcodes.SETUP_FINALLY)
def setup_finally(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    exception_handle_stack.append(instr.arg_value)
    return instr.next_instruction, func


@execution(Opcodes.POP_BLOCK)
def pop_block(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    exception_handle_stack.pop(-1)
    return instr.next_instruction, func


@execution(Opcodes.IMPORT_NAME)
def import_name(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(importlib.import_module(instr.arg_value))
    return instr.next_instruction, func


@execution(Opcodes.IMPORT_FROM)
def import_name(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(getattr(stack.pop(-1), instr.arg_value))
    return instr.next_instruction, func


@execution(Opcodes.GET_ITER)
def get_iter(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(iter(stack.pop(-1)))
    return instr.next_instruction, func


@execution(Opcodes.FOR_ITER)
def for_iter(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:

    iterator = stack[-1]

    try:
        stack.append(next(iterator))
    except StopIteration:
        stack.pop(-1)
        return instr.arg_value, func

    return instr.next_instruction, func


@execution(Opcodes.BUILD_TUPLE)
def build_tuple(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack.append(tuple(reversed([stack.pop(-1) for _ in range(instr.arg)])))
    return instr.next_instruction, func


@execution(Opcodes.UNPACK_SEQUENCE)
def unpack_sequence(func: MutableFunction, instr: Instruction, stack: list, local: list, call_stack: list, exception_handle_stack: list) -> typing.Tuple[Instruction, MutableFunction]:
    stack += reversed(stack.pop(-1))
    return instr.next_instruction, func
