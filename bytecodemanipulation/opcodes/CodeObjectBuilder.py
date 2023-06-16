import typing


if typing.TYPE_CHECKING:
    from bytecodemanipulation.opcodes.Instruction import Instruction
    from bytecodemanipulation.MutableFunction import MutableFunction


class CodeObjectBuilder:
    def __init__(self, function: "MutableFunction"):
        self.function = function
        self.temporary_instructions: typing.List["Instruction"] = []

        self.shared_variable_names = function.argument_names.copy()
        self.constants = []
        self.shared_names = []
        self.free_variables = []
        self.cell_variables = []

        self.first_line_number = 0
        self.line_info_table = bytes()

    def prepare_previous_instructions(self):
        for instruction in self.temporary_instructions:
            if instruction.previous_instructions:
                instruction.previous_instructions.clear()

        for instruction in self.temporary_instructions:
            if instruction.has_stop_flow() or instruction.has_unconditional_jump():
                continue

            instruction.next_instruction.add_previous_instruction(instruction)

            if instruction.has_jump():
                # print(instruction.arg_value, typing.cast, typing.cast(Instruction, instruction.arg_value))

                typing.cast(
                    Instruction, instruction.arg_value
                ).add_previous_instruction(instruction)

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

