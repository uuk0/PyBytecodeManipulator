import typing

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes, HAS_GLOBAL
from bytecodemanipulation.opcodes.Opcodes import UNCONDITIONAL_JUMPS


class Guarantees:
    class AbstractGuarantee:
        pass

    RESULT_IS_CONSTANT = AbstractGuarantee()
    NO_DISCARD = AbstractGuarantee()

    class ArgIsNotMutated(AbstractGuarantee):
        def __init__(self, arg_index: int, arg_name: str):
            self.arg_index = arg_index
            self.arg_name = arg_name

    class ReturnType(AbstractGuarantee):
        def __init__(self, data_type: type, may_subclass=False):
            self.data_type = data_type
            self.may_subclass = may_subclass


class MethodInvocationInfo:
    def __init__(self, call_instruction: Instruction):
        self.call_instruction = call_instruction

        if call_instruction.opcode == Opcodes.CALL_FUNCTION:
            self.arg_loads = [
                next(call_instruction.trace_stack_position(i))
                for i in range(call_instruction.arg - 1, -1, -1)
            ]
            self.function_load = call_instruction.trace_normalized_stack_position(
                call_instruction.arg
            )
        else:
            raise NotImplementedError(call_instruction)

        self._guarantees: typing.List[Guarantees.AbstractGuarantee] = None

    def get_guarantees(self) -> typing.List[Guarantees.AbstractGuarantee]:
        if self._guarantees:
            return self._guarantees

        if self.function_load.opcode != Opcodes.LOAD_CONST:
            return []

        from bytecodemanipulation.Optimiser import _OptimisationContainer

        function_target = self.function_load.arg_value
        optimisation_container = _OptimisationContainer.get_for_target(function_target)

        self._guarantees = []
        if optimisation_container.guarantees:
            self._guarantees += optimisation_container.guarantees

        return self._guarantees

    def is_argument_mutated(self, name_or_index: str | int) -> bool:
        for guarantee in self.get_guarantees():
            if isinstance(guarantee, Guarantees.ArgIsNotMutated) and (
                guarantee.arg_index == name_or_index
                or guarantee.arg_name == name_or_index
            ):
                return False

        return True


def prefix_all_locals_with_all(
    mutable: MutableFunction,
    prefix: str,
):
    def add_prefix(instr: Instruction):
        if instr.has_local():
            instr.arg_value = prefix + instr.arg_value

    mutable.walk_instructions(add_prefix)


def prefix_all_locals_with_specified(
    mutable: MutableFunction,
    prefix: str,
    protected_locals: typing.List[str] = tuple(),
):
    def add_prefix(instr: Instruction):
        if instr.has_local() and instr.arg_value not in protected_locals:
            instr.arg_value = prefix + instr.arg_value

    mutable.walk_instructions(add_prefix)


def replace_opcode_with_other(
    mutable: MutableFunction,
    old_opcode: int,
    new_opcode: int,
    handle_new: typing.Callable[[Instruction], None] = lambda _: None,
):
    def replace(instruction: Instruction):
        if instruction.opcode == old_opcode:
            instruction.change_opcode(new_opcode)

            handle_new(instruction)

    mutable.walk_instructions(replace)


def inline_access_to_global(
    mutable: MutableFunction, global_name: str, value=...
):
    if value == ...:
        value = mutable.target.__globals__[global_name]

    def replace(instruction: Instruction):
        if instruction.opcode == Opcodes.LOAD_GLOBAL:
            if instruction.arg_value == global_name:
                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(value)

    mutable.walk_instructions(replace)


def replace_const_func_call_with_opcode(
    mutable: MutableFunction,
    func: typing.Callable,
    opcode: int,
    handle_args: typing.Callable[
        [MutableFunction, Instruction, typing.List[Instruction]], bool
    ],
):
    def visitor(instruction: Instruction):
        if instruction.opcode == Opcodes.CALL_FUNCTION:
            counter = instruction.arg
            args = [next(instruction.trace_stack_position(i)) for i in range(instruction.arg)]
            load_method = next(instruction.trace_stack_position(instruction.arg))

            if (
                load_method.opcode == Opcodes.LOAD_CONST
                and load_method.arg_value == func
                and all(instr.opcode == Opcodes.LOAD_CONST for instr in args)
            ):
                instruction.change_opcode(opcode)
                if not handle_args(mutable, instruction, args):
                    instruction.change_opcode(Opcodes.CALL_FUNCTION)

    mutable.walk_instructions(visitor)


def capture_local(name: str):
    pass


def outer_return(value=None):
    pass


def _inline_capture_local(
    mutable: MutableFunction,
    instruction: Instruction,
    args: typing.List[Instruction],
) -> bool:
    if len(args) != 1:
        return False
    if args[0].opcode != Opcodes.LOAD_CONST:
        return False

    instruction.arg = args[0].arg
    instruction.arg_value = args[0].arg_value
    args[0].change_opcode(Opcodes.NOP)
    args[0].arg = 0
    args[0].arg_value = None

    return True


def _inline_outer_return(
    mutable: MutableFunction,
    instruction: Instruction,
    args: typing.List[Instruction],
) -> bool:
    if len(args) > 1:
        return False
    if len(args) > 0 and args[0].opcode != Opcodes.LOAD_CONST:
        return False

    # In case we have no args, we need to add a LOAD_CONST(None)
    if len(args) == 0:
        instruction.change_opcode(Opcodes.LOAD_CONST)
        instruction.change_arg_value(None)
        return_instr = Instruction.create_with_same_info(instruction, Opcodes.RETURN_VALUE)
        return_instr.next_instruction = instruction.next_instruction
        instruction.next_instruction = return_instr

    return True


def insert_method_into(
    body: MutableFunction,
    entry_point: typing.Union[Instruction, int],
    to_insert: MutableFunction,
    protected_locals: typing.List[str] = tuple(),
    drop_return_result=True,
):
    """
    Inserts the function AFTER the given offset / Instruction.
    If wanted at HEAD, set offset to -1
    """

    if entry_point == -1:
        HEAD_INSTRUCTION = Instruction("NOP")
        HEAD_INSTRUCTION.function = body
        HEAD_INSTRUCTION.next_instruction = body.instruction_entry_point
        body.instruction_entry_point = HEAD_INSTRUCTION

    elif isinstance(entry_point, int):
        head = body.instruction_entry_point

        for _ in range(entry_point):
            if not head.has_unconditional_jump():
                head = head.next_instruction
            else:
                head = head.arg_value

        HEAD_INSTRUCTION = head
        del head

    elif isinstance(entry_point, Instruction):
        HEAD_INSTRUCTION = entry_point

    else:
        raise ValueError(entry_point)

    def set_offset(instr):
        instr.offset = -1

    to_insert.walk_instructions(set_offset)

    if protected_locals is not None:
        prefix_all_locals_with_specified(
            to_insert, to_insert.function_name + ":", protected_locals
        )
    else:
        prefix_all_locals_with_all(to_insert, to_insert.function_name + ":")

    replace_opcode_with_other(
        to_insert, Opcodes.RETURN_VALUE, Opcodes.INTERMEDIATE_INNER_RETURN
    )
    inline_access_to_global(to_insert, "capture_local", capture_local)
    inline_access_to_global(to_insert, "outer_return", outer_return)

    # MutableFunctionWithTree(to_insert).print_recursive()

    instr: Instruction = None
    previous: Instruction = None

    def visit(instr):
        nonlocal previous

        if previous is not None:
            previous.next_instruction = instr

        if instr.opcode == Opcodes.INTERMEDIATE_INNER_RETURN:
            if drop_return_result:
                previous.insert_after(Instruction.create_with_same_info(previous, Opcodes.POP_TOP))

            instr.change_opcode(
                Opcodes.JUMP_ABSOLUTE, HEAD_INSTRUCTION.next_instruction
            )

        previous = instr

    to_insert.walk_instructions(visit)

    if instr is not None and instr.next_instruction is None:
        instr.next_instruction = HEAD_INSTRUCTION.next_instruction

    replace_const_func_call_with_opcode(
        to_insert,
        capture_local,
        Opcodes.LOAD_FAST,
        _inline_capture_local,
    )
    replace_const_func_call_with_opcode(
        to_insert,
        outer_return,
        Opcodes.RETURN_VALUE,
        _inline_outer_return,
    )

    HEAD_INSTRUCTION.next_instruction = to_insert.instruction_entry_point


def inline_calls_to_const_functions(mutable: MutableFunction, builder):
    from bytecodemanipulation.Optimiser import _OptimisationContainer

    dirty = False

    def visit(instr: Instruction):
        if instr.opcode == Opcodes.CALL_FUNCTION:
            source = next(instr.trace_stack_position(instr.arg))

            if source.opcode != Opcodes.LOAD_CONST:
                return

            target = source.arg_value

            container = _OptimisationContainer.get_for_target(target)
            if not container.try_inline_calls:
                return

            instr.change_opcode(Opcodes.NOP)
            insert_method_into(
                mutable,
                instr,
                MutableFunction(target),
                drop_return_result=False,
            )
            source.change_opcode(Opcodes.NOP)
            nonlocal dirty
            dirty = True

    mutable.walk_instructions(visit)
    return dirty
