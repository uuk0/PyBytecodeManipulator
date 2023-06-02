import typing


if typing.TYPE_CHECKING:
    from bytecodemanipulation.opcodes.Instruction import Instruction
    from bytecodemanipulation.MutableFunction import MutableFunction


class CodeObjectBuilder:
    def __init__(self, function: "MutableFunction"):
        self.function = function
        self.temporary_instructions: typing.List["Instruction"] = []

        self.shared_variable_names = []
        self.constants = []
        self.shared_names = []
        self.free_variables = []
        self.cell_variables = []

    def reserve_local_name(self, name: str) -> int:
        if name in self.shared_variable_names:
            return self.shared_variable_names.index(name)
        self.shared_variable_names.append(name)
        return len(self.shared_variable_names) - 1

    def reserve_cell_name(self, name: str) -> int:
        if name in self.cell_variables:
            return self.cell_variables.index(name)
        self.cell_variables.append(name)
        return len(self.cell_variables) - 1

    def reserve_name(self, name: str) -> int:
        if name in self.shared_names:
            return self.shared_names.index(name)
        self.shared_names.append(name)
        return len(self.shared_names) - 1

    def reserve_constant(self, constant: typing.Any) -> int:
        if constant in self.constants:
            return self.constants.index(constant)
        self.constants.append(constant)
        return len(self.constants) - 1

