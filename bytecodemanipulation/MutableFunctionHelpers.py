import typing

from bytecodemanipulation.MutableFunction import MutableFunction, Instruction
from bytecodemanipulation.Opcodes import Opcodes, HAS_GLOBAL
from bytecodemanipulation.Opcodes import UNCONDITIONAL_JUMPS


class MutableFunctionWithTree:
    def __init__(self, mutable: MutableFunction, root: Instruction = None):
        self.mutable = mutable
        self.root = root or mutable.instructions[0]

    def visitor(self, visitor: typing.Callable[[Instruction, typing.List[Instruction]], None]):
        def visit(instruction: Instruction, visited: typing.Set[Instruction], path: typing.List[Instruction]):
            visitor(instruction, path)

            if instruction in visited:
                return

            visited.add(instruction)

            if not instruction.has_stop_flow():
                visit(instruction.next_instruction, visited, path + [instruction])

            if instruction.has_jump():
                # visit the jump target, but reset the instruction path, as we cannot make sure that
                # it is the only path leading there
                # TODO: is there a better way? (first visit the main tree, and than branch?)
                visit(instruction.arg_value, visited, [instruction])

        visit(self.root, set(), [])

    def print_recursive(self, root: Instruction = None, visited: set = None, level=0):
        if root is None:
            print("Starting Dump...")
            root = self.root

        if visited is None:
            visited = set()
        elif root in visited:
            return

        print(" "*level + repr(root), "-> -1" if root.next_instruction is None else "-> "+str(root.next_instruction.offset))
        visited.add(root)

        if root.has_stop_flow(): return

        if root.next_instruction is None:
            print("-" * level, "END OF CONTROL FLOW")
            return

        self.print_recursive(root.next_instruction, visited, level)

        if root.has_jump():
            self.print_recursive(root.arg_value, visited, level+1)


def prefix_all_locals_with(
    mutable: MutableFunction | MutableFunctionWithTree, prefix: str
):
    if isinstance(mutable, MutableFunctionWithTree):
        mutable.mutable.assemble_instructions_from_tree(mutable.root)
        mutable = mutable.mutable

    mutable.shared_variable_names = [prefix + e for e in mutable.shared_variable_names]

    for instruction in mutable.instructions:
        if instruction.has_local():
            instruction.update_owner(mutable, instruction.offset)


def replace_opcode_with_other(
    mutable: MutableFunction | MutableFunctionWithTree, old_opcode: int, new_opcode: int, handle_new: typing.Callable[[Instruction], None] = lambda _: None
):
    if isinstance(mutable, MutableFunctionWithTree):
        mutable.mutable.assemble_instructions_from_tree(mutable.root)
        mutable = mutable.mutable

    for instruction in mutable.instructions:
        if instruction.opcode == old_opcode:
            instruction.change_opcode(new_opcode)

            handle_new(instruction)


def inline_access_to_global(mutable: MutableFunction | MutableFunctionWithTree, global_name: str, value=...):
    if isinstance(mutable, MutableFunctionWithTree):
        mutable.mutable.assemble_instructions_from_tree(mutable.root)
        mutable = mutable.mutable

    if value == ...:
        value = mutable.target.__globals__[global_name]

    for i, instruction in enumerate(mutable.instructions):
        if instruction.opcode == Opcodes.LOAD_GLOBAL:
            if instruction.arg_value == global_name:
                instruction.change_opcode(Opcodes.LOAD_CONST)
                instruction.change_arg_value(value)


def replace_const_func_call_with_opcode(mutable: MutableFunctionWithTree, func: typing.Callable, opcode: int, handle_args: typing.Callable[[MutableFunctionWithTree, Instruction, typing.List[Instruction]], bool]):
    def visitor(instruction: Instruction, path: typing.List[Instruction]):
        if instruction.opcode == Opcodes.CALL_FUNCTION:
            counter = instruction.arg
            args = path[-counter:]
            load_method = path[-counter-1]

            if load_method.opcode == Opcodes.LOAD_CONST and load_method.arg_value == func and all(instr.opcode == Opcodes.LOAD_CONST for instr in args):
                instruction.change_opcode(opcode)
                if not handle_args(mutable, instruction, args):
                    instruction.change_opcode(Opcodes.CALL_FUNCTION)

    mutable.visitor(visitor)


def capture_local(name: str):
    pass


def outer_return(value=None):
    pass


def _inline_capture_local(tree: MutableFunctionWithTree, instruction: Instruction, args: typing.List[Instruction]) -> bool:
    if len(args) != 1: return False
    if args[0].opcode != Opcodes.LOAD_CONST: return False

    instruction.arg = args[0].arg
    instruction.arg_value = args[0].arg_value
    args[0].change_opcode(Opcodes.NOP)
    args[0].arg = 0
    args[0].arg_value = None

    return True


def _inline_outer_return(tree: MutableFunctionWithTree, instruction: Instruction, args: typing.List[Instruction]) -> bool:
    if len(args) > 1: return False
    if len(args) > 0 and args[0].opcode != Opcodes.LOAD_CONST: return False

    # In case we have no args, we need to add a LOAD_CONST(None)
    if len(args) == 0:
        instruction.change_opcode(Opcodes.LOAD_CONST)
        instruction.change_arg_value(None)
        return_instr = Instruction(Opcodes.RETURN_VALUE)
        return_instr.update_owner(tree.mutable, -1)
        return_instr.next_instruction = instruction.next_instruction
        instruction.next_instruction = return_instr

    return True


def insert_method_into(
    body: MutableFunction | MutableFunctionWithTree,
    offset: typing.Union[Instruction, int],
    to_insert: MutableFunction | MutableFunctionWithTree,
):
    """
    Inserts the function AFTER the given offset / Instruction.
    If wanted at HEAD, set offset to -1
    """

    if isinstance(to_insert, MutableFunctionWithTree):
        to_insert.mutable.assemble_instructions_from_tree(to_insert.root)
        to_insert = to_insert.mutable

    if not isinstance(body, MutableFunctionWithTree):
        body = MutableFunctionWithTree(body)

    if offset == -1:
        HEAD_INSTRUCTION = Instruction("NOP")
        HEAD_INSTRUCTION.function = body.mutable
        HEAD_INSTRUCTION.next_instruction = body.root
        body.root = HEAD_INSTRUCTION
    elif isinstance(offset, int):
        body.mutable.assemble_instructions_from_tree(body.root)
        HEAD_INSTRUCTION = body.mutable.instructions[offset]
    else:
        HEAD_INSTRUCTION = offset

    for instr in to_insert.instructions:
        instr.offset = -1

    prefix_all_locals_with(to_insert, to_insert.function_name + ":")
    replace_opcode_with_other(to_insert, Opcodes.RETURN_VALUE, Opcodes.INTERMEDIATE_INNER_RETURN)
    inline_access_to_global(to_insert, "capture_local", capture_local)
    inline_access_to_global(to_insert, "outer_return", outer_return)

    MutableFunctionWithTree(to_insert).print_recursive()

    instr = None
    previous = None
    for instr in to_insert.instructions:
        if previous is not None:
            previous.next_instruction = instr

        if instr.opcode == Opcodes.INTERMEDIATE_INNER_RETURN:
            previous.next_instruction = Instruction(Opcodes.POP_TOP)
            previous.next_instruction.update_owner(to_insert, -1)
            previous.next_instruction.next_instruction = instr

            instr.change_opcode(Opcodes.JUMP_ABSOLUTE)
            instr.change_arg_value(HEAD_INSTRUCTION.next_instruction)

        previous = instr

    if instr is not None and instr.next_instruction is None:
        instr.next_instruction = HEAD_INSTRUCTION.next_instruction

    to_insert.assemble_instructions_from_tree(to_insert.instructions[0], breaks_flow=(Instruction(Opcodes.JUMP_ABSOLUTE, HEAD_INSTRUCTION.next_instruction),))
    to_insert.decode_instructions()

    to_insert_tree = MutableFunctionWithTree(to_insert)
    to_insert_tree.print_recursive()
    replace_const_func_call_with_opcode(
        to_insert_tree,
        capture_local,
        Opcodes.LOAD_FAST,
        _inline_capture_local,
    )
    to_insert_tree.print_recursive()
    replace_const_func_call_with_opcode(
        to_insert_tree,
        outer_return,
        Opcodes.RETURN_VALUE,
        _inline_outer_return,
    )
    to_insert_tree.print_recursive()

    def visit(instruction: Instruction, path):
        if instruction is None:
            print(path)
            raise

        instruction.function = body.mutable

        if instruction.has_constant():
            instruction.arg = body.mutable.allocate_shared_constant(instruction.arg_value)
        elif instruction.has_name():
            instruction.arg = body.mutable.allocate_shared_name(instruction.arg_value)
        elif instruction.has_local():
            instruction.arg = body.mutable.allocate_shared_variable_name(instruction.arg_value)

    HEAD_INSTRUCTION.next_instruction = to_insert_tree.root
    body.visitor(visit)

    body.print_recursive()

    body.mutable.assemble_instructions_from_tree(body.root)

    body.print_recursive()
