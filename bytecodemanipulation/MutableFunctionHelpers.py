from bytecodemanipulation.MutableFunction import MutableFunction


class MutableFunctionWithTree:
    def __init__(self, mutable: MutableFunction):
        self.mutable = mutable
        self.root = mutable.instructions[0]


def prefix_all_locals_with(mutable: MutableFunction | MutableFunctionWithTree, prefix: str):
    if isinstance(mutable, MutableFunctionWithTree):
        mutable.mutable.assemble_instructions_from_tree(mutable.root)
        mutable = mutable.mutable

    mutable.shared_variable_names = [
        prefix + e
        for e in mutable.shared_variable_names
    ]

    for instruction in mutable.instructions:
        if instruction.has_local():
            instruction.update_owner(mutable, instruction.offset)

