import copy
import dis
import sys
import types
import typing
import simplejson

from bytecodemanipulation.Instruction import Instruction
from bytecodemanipulation.Opcodes import (
    Opcodes,
)
import bytecodemanipulation.data_loader


class LinearCodeConstraintViolationException(Exception):
    pass


class MutableFunction:
    @classmethod
    def create(cls, target):
        if isinstance(target, staticmethod):
            return cls(target.__func__)
        elif isinstance(target, classmethod):
            return cls(target.__func__)
        return cls(target)

    def __init__(self, target: types.FunctionType | types.MethodType):
        self.target = target

        self.code_object: types.CodeType = target.__code__

        self._load_from_code_object(self.code_object)

    if sys.version_info.major == 3 and sys.version_info.minor == 10:

        def _load_from_code_object(self, obj: types.CodeType):
            self.argument_count = self.code_object.co_argcount
            self.cell_variables = list(self.code_object.co_cellvars)
            self.__raw_code = bytearray(self.code_object.co_code)
            self.constants = list(self.code_object.co_consts)
            self.filename = self.code_object.co_filename
            self.first_line_number = self.code_object.co_firstlineno
            self.code_flags = self.code_object.co_flags
            self.free_variables = list(self.code_object.co_freevars)
            self.keyword_only_argument_count = self.code_object.co_kwonlyargcount
            self.line_table = self.code_object.co_linetable
            self.lnotab = bytearray(self.code_object.co_lnotab)

            self.function_name = self.code_object.co_name
            self.shared_names = list(self.code_object.co_names)
            # Local variable count is implied by co_varnames
            self.positional_only_argument_count = self.code_object.co_posonlyargcount
            self.stack_size = self.code_object.co_stacksize
            self.shared_variable_names = list(self.code_object.co_varnames)

            self.__instructions: typing.Optional[typing.List[Instruction]] = None

    elif sys.version_info.major == 3 and sys.version_info.minor == 11:

        def _load_from_code_object(self, obj: types.CodeType):
            self.argument_count = self.code_object.co_argcount
            self.cell_variables = list(self.code_object.co_cellvars)
            self.__raw_code = bytearray(self.code_object.co_code)
            self.constants = list(self.code_object.co_consts)
            self.filename = self.code_object.co_filename
            self.first_line_number = self.code_object.co_firstlineno
            self.code_flags = self.code_object.co_flags
            self.free_variables = list(self.code_object.co_freevars)
            self.keyword_only_argument_count = self.code_object.co_kwonlyargcount
            self.line_table = self.code_object.co_linetable
            self.lnotab = bytearray(self.code_object.co_lnotab)

            self.function_name = self.code_object.co_name
            self.shared_names = list(self.code_object.co_names)
            # Local variable count is implied by co_varnames
            self.positional_only_argument_count = self.code_object.co_posonlyargcount
            self.stack_size = self.code_object.co_stacksize
            self.shared_variable_names = list(self.code_object.co_varnames)

            self.exception_table = bytearray(self.code_object.co_exceptiontable)

            self.__instructions: typing.Optional[typing.List[Instruction]] = None

    else:
        raise RuntimeError(sys.version_info)

    def __repr__(self):
        return f"MutableFunction({self.target})"

    def copy(self):
        def _():
            pass

        instance = type(self)(_)
        instance.copy_from(self)

        return instance

    def copy_from(self, mutable: "MutableFunction"):
        # self.target = mutable.target
        self.code_object = mutable.code_object

        self.argument_count = mutable.argument_count
        self.cell_variables = mutable.cell_variables.copy()
        self.__raw_code = mutable.raw_code.copy()
        self.constants = copy.deepcopy(mutable.constants)
        self.filename = mutable.filename
        self.first_line_number = mutable.first_line_number
        self.code_flags = mutable.code_flags
        self.free_variables = mutable.free_variables.copy()
        self.keyword_only_argument_count = mutable.keyword_only_argument_count
        self.line_table = copy.copy(mutable.line_table)
        self.lnotab = mutable.lnotab
        self.function_name = mutable.function_name
        self.shared_names = mutable.shared_names.copy()
        self.positional_only_argument_count = mutable.positional_only_argument_count
        self.stack_size = mutable.stack_size
        self.shared_variable_names = mutable.shared_variable_names.copy()

        self.__instructions = None

    if sys.version_info.major == 3 and sys.version_info.minor == 10:

        def create_code_obj(self) -> types.CodeType:
            if self.__instructions is None:
                self.get_instructions()

            self.assemble_fast(self.__instructions)

            return types.CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                len(self.shared_variable_names),
                self.stack_size,
                self.code_flags,
                bytes(self.raw_code),
                tuple(self.constants),
                tuple(self.shared_names),
                tuple(self.shared_variable_names),
                self.filename,
                self.function_name,
                self.first_line_number,
                self.get_lnotab(),
                tuple(self.free_variables),
                tuple(self.cell_variables),
            )

    elif sys.version_info.major == 3 and sys.version_info.minor == 11:

        def create_code_obj(self) -> types.CodeType:
            if self.__instructions is None:
                self.get_instructions()

            self.assemble_fast(self.__instructions)

            return types.CodeType(
                self.argument_count,
                self.positional_only_argument_count,
                self.keyword_only_argument_count,
                len(self.shared_variable_names),
                self.stack_size,
                self.code_flags,
                bytes(self.raw_code),
                tuple(self.constants),
                tuple(self.shared_names),
                tuple(self.shared_variable_names),
                self.filename,
                self.function_name,
                self.function_name,
                self.first_line_number,
                self.get_lnotab(),
                bytes(self.exception_table),
                tuple(self.free_variables),
                tuple(self.cell_variables),
            )

    def get_lnotab(self) -> bytes:
        items = []

        prev_line = self.first_line_number
        count_since_previous = 0

        for instr in self.__instructions:
            count_since_previous += 1

            if instr.source_location is None or instr.source_location[0] == prev_line:
                continue

            offset = instr.source_location[0] - prev_line

            if offset > 127:
                return bytes()

            if offset < 0:
                return bytes()

            items.append(count_since_previous)
            items.append(offset)
            count_since_previous = 0

        return bytes(items)

    def calculate_max_stack_size(self) -> int:
        stack_size_table = self.get_max_stack_size_table()

        self.stack_size = max(max(stack_size_table), 0)
        return self.stack_size

    def get_max_stack_size_table(
        self, instructions: typing.List[Instruction] = None
    ) -> typing.List[int]:
        stack_size_table = [-1] * len(instructions or self.instructions)

        if not instructions:
            self.prepare_previous_instructions()

        for i, instr in enumerate(instructions or self.instructions):
            stack = -1
            if i != 0:
                prev = (instructions or self.instructions)[i - 1]

                if not prev.has_stop_flow() and not prev.has_unconditional_jump():
                    stack = stack_size_table[i - 1]
            else:
                stack = 0

            if instr.previous_instructions:
                for instruction in instr.previous_instructions:
                    if stack_size_table[instruction.offset] != -1:
                        stack = max(stack, stack_size_table[instruction.offset])
                        stack += instruction.special_stack_affect_when_followed_by(
                            instr
                        )

            if stack != -1:
                add, sub, _ = instr.get_stack_affect()
                stack += add
                stack -= sub

            stack_size_table[i] = stack

        if -1 in stack_size_table:
            pending = list(filter(lambda e: e[1] == -1, enumerate(stack_size_table)))
            last_next = -1

            while pending:
                i, _ = pending.pop(0)
                instr = (instructions or self.instructions)[i]
                stack = -1

                if i == last_next:
                    break

                if not instr.previous_instructions:
                    print("WARN:", instr)
                    continue

                for instruction in instr.previous_instructions:
                    if stack_size_table[instruction.offset] != -1:
                        stack = max(stack, stack_size_table[instruction.offset])
                        stack += instruction.special_stack_affect_when_followed_by(
                            instr
                        )

                if stack != -1:
                    add, sub, _ = instr.get_stack_affect()
                    stack += add
                    stack -= sub

                    stack_size_table[i] = stack

                    if pending:
                        last_next = pending[0][0]
                else:
                    pending.append((i, -1))

                if last_next == -1:
                    last_next = i

        return stack_size_table

    def reassign_to_function(self):
        self.calculate_max_stack_size()
        self.target.__code__ = self.create_code_obj()

    def decode_instructions(self):
        if self.__instructions is not None:
            self.__instructions.clear()
        else:
            self.__instructions = []

        line = self.first_line_number
        lnotab = list(self.lnotab)

        extra: int = 0
        for i in range(0, len(self.__raw_code), 2):
            opcode, arg = self.__raw_code[i : i + 2]

            if opcode == Opcodes.EXTENDED_ARG:
                extra = extra * 256 + arg
                instr = Instruction(self, i // 2, "NOP", _decode_next=False)

            else:
                arg += extra * 256
                extra = 0

                if opcode in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                    arg += 1

                instr = Instruction(self, i // 2, opcode, arg=arg, _decode_next=False)

            if lnotab:
                lnotab[0] -= 1

                if lnotab[0] == 0:
                    line_incr = lnotab[1]
                    del lnotab[:2]

                    line += line_incr

            instr.source_location = (line, None, None)

            self.__instructions.append(instr)
            # print(instr, instr.source_location)

        for i, instruction in enumerate(self.instructions):
            instruction.update_owner(self, i)

        self.prepare_previous_instructions()

    def prepare_previous_instructions(self):
        for instruction in self.instructions:
            if instruction.previous_instructions:
                instruction.previous_instructions.clear()

        for instruction in self.instructions:
            if instruction.has_stop_flow() or instruction.has_unconditional_jump():
                continue

            instruction.next_instruction.add_previous_instruction(instruction)

            if instruction.has_jump():
                # print(instruction.arg_value, typing.cast, typing.cast(Instruction, instruction.arg_value))

                typing.cast(
                    Instruction, instruction.arg_value
                ).add_previous_instruction(instruction)

    def assemble_instructions_from_tree(self, root: Instruction, breaks_flow=tuple()):
        # 1. Assemble a linear stream of instructions, containing all instructions
        # 2. check instructions which require unconditional JUMP's and insert them
        # 3. update instruction positions
        # 4. Update the arg value of jumps
        # 5. Walk over all instructions and set extended arg count + insert NOP's, and recheck if instructions need more extended
        # 6. Resolve jump target into real values
        # 7. Profit! (Maybe use assemble_fast() here!

        instructions = self.assemble_linear_instructions(breaks_flow, root)

        self.update_instruction_offsets(instructions)

        self.insert_needed_jumps(instructions)

        self.update_instruction_offsets(instructions)

        self.update_jump_args(instructions)
        required_extends = self.get_required_arg_extensions(instructions)
        self.insert_required_nops(instructions, required_extends)
        self.update_jump_args(instructions)

        # Check how many EXTENDED_ARG we really need
        required_extends_2 = self.get_required_arg_extensions(instructions)

        if required_extends != required_extends_2:
            # todo: here, walk again over the instruction list
            raise NotImplementedError

        # For a last time, walk over the instructions and tie them together
        for i, instruction in enumerate(instructions[:]):
            if (
                not instruction.has_stop_flow()
                and not instruction.has_unconditional_jump()
            ):
                try:
                    instruction.next_instruction = instructions[i + 1]
                except IndexError:
                    instruction.next_instruction = None
                except:
                    print(instruction)
                    print(instruction.next_instruction)
                    raise

        self.assemble_fast(instructions)
        self.update_instruction_offsets(self.instructions)
        # We do not re-decode, as that would invalidate the instruction instances here

    def update_instruction_offsets(self, instructions):
        # Update instruction positions
        for i, instruction in enumerate(instructions):
            instruction.offset = i

    def insert_required_nops(self, instructions, required_extends):
        write_offset = 0
        # Now insert the required NOP's
        for instruction, count in zip(instructions[:], required_extends):
            if count == 0:
                continue

            for _ in range(count):
                pos = instruction.offset + write_offset
                instructions.insert(
                    pos, nop_instr := Instruction.create(self, pos, "NOP")
                )

            write_offset += count

    def get_required_arg_extensions(self, instructions):
        # Check how many EXTENDED_ARG we need
        required_extends = [0] * len(instructions)
        for i, instruction in enumerate(instructions):
            arg = instruction.arg

            if arg is None:
                if instruction.opcode < dis.HAVE_ARGUMENT:
                    arg = 0
                else:
                    print("error", instruction)

            if arg >= 256**3:
                count = 3
            elif arg >= 256**2:
                count = 2
            elif arg >= 256:
                count = 1
            else:
                count = 0
            required_extends[i] = count
        return required_extends

    def update_jump_args(self, instructions):
        # Update the raw arg for jumps
        for i, instruction in enumerate(instructions):
            if instruction.next_instruction is None:
                continue

            instruction.update_owner(self, i)

            if instruction.has_jump_absolute():
                instruction.change_arg_value(instruction.arg_value)
            elif instruction.offset in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                instruction.change_arg_value(instruction.arg_value)
            elif instruction.has_jump_forward():
                instruction.change_arg_value(instruction.arg_value)
            elif instruction.has_jump_backward():
                instruction.change_arg_value(instruction.arg_value)

    def insert_needed_jumps(self, instructions):
        # Check for unconditional jumps required
        for instruction in instructions[:]:
            if instruction.has_stop_flow():
                continue

            # FOR_ITER can only jump FORWARD, so insert a new jump absolute to jump there
            # TODO: insert the JUMP somewhere else than here!
            if instruction.opcode == Opcodes.FOR_ITER:
                jump = Instruction(
                    self,
                    -1,
                    "JUMP_ABSOLUTE",
                    instruction.next_instruction,
                )
                jump.change_arg_value(instruction.arg_value)
                instruction.change_arg_value(jump)
                instructions.append(jump)

            if (
                instruction.next_instruction is not None
                and instruction.offset + 1 != instruction.next_instruction.offset
            ):
                jump = Instruction(
                    self,
                    -1,
                    "JUMP_ABSOLUTE",
                    instruction.next_instruction,
                )
                jump.next_instruction = instruction
                instruction.next_instruction = jump
                instructions.insert(instructions.index(instruction) + 1, jump)

    def assemble_linear_instructions(self, breaks_flow, root):

        # While we have branches, we need to decode them
        pending_instructions = [root]
        visited: typing.Set[Instruction] = set()
        instructions: typing.List[Instruction] = []

        while pending_instructions:
            instruction = pending_instructions.pop()

            if not isinstance(instruction, Instruction):
                print(f"Invalid task instruction: {instruction}")
                continue

            if not isinstance(instruction, Instruction):
                raise ValueError(instruction)

            # If we visited it, we can skip
            if instruction in visited:
                continue

            # Walk over the instructions as long as we have not met them
            while instruction not in visited:
                if not isinstance(instruction, Instruction):
                    print(f"Invalid task instruction: {instruction}")
                    break

                # If it branches off, it needs to be visited later on
                if instruction.has_jump():
                    if instruction.arg_value is None:
                        instruction.update_owner(self, instruction.offset)

                    assert instruction.arg_value is not None, instruction

                    pending_instructions.append(instruction.arg_value)

                instructions.append(instruction)
                visited.add(instruction)

                if (
                    instruction.has_stop_flow()
                    or instruction in breaks_flow
                    or instruction.opcode in breaks_flow
                ):
                    break

                if instruction.next_instruction is None:
                    instruction.update_owner(self, instruction.offset)

                # The next instruction MUST be set if it does NOT end the control flow
                if instruction.next_instruction is None:
                    print("---- start dump")
                    for instr in instructions:
                        print(instr)
                    print("---- end dump")
                    raise RuntimeError(f"next instruction is None: {instruction}")

                instruction = instruction.next_instruction

        return instructions

    def assemble_instructions(self):

        # Check for linearity violations
        for i, instruction in enumerate(self.__instructions):
            if (
                instruction.next_instruction is not None
                and instruction.offset + 1 != instruction.next_instruction.offset
                and not instruction.has_unconditional_jump()
                and not instruction.has_stop_flow()
            ):
                # todo: do we want to dynamic use assemble_instructions_from_tree()?
                raise LinearCodeConstraintViolationException(
                    f"Failed between instruction {instruction} and {instruction.next_instruction}, use assemble_instructions_from_tree(...) to assemble from an non-normal tree"
                )

        needs_tree_assemble = False
        root = self.__instructions[0]
        previous = None

        # Check if the NOP's ahead of instructions are enough to hold the extra args
        nop_count = 0
        for i, instruction in enumerate(self.__instructions):
            if instruction.opname == "NOP":
                nop_count += 1
                previous = instruction
                continue

            if instruction.arg is not None:
                if instruction.arg >= 256**3:
                    count = 3
                elif instruction.arg >= 256**2:
                    count = 2
                elif instruction.arg >= 256:
                    count = 1
                else:
                    count = 0

                # Are there NOP's missing for the needed EXTENDED_ARG?
                if count > nop_count:
                    # todo: move this code up into assemble_instructions_from_tree()

                    missing = count - nop_count  # how many we need
                    needs_tree_assemble = True  # make sure that we use the assemble_instructions_from_tree() now

                    # If we are at HEAD, we require some clever handling, as "previous" is None at the moment
                    if i == 0:
                        root = previous = Instruction(
                            self,
                            0,
                            "NOP",
                        )
                        root.next_instruction = instruction
                        missing -= 1

                    previous.insert_after(
                        [
                            Instruction(self, previous.offset + i + 1, Opcodes.NOP)
                            for i in range(missing)
                        ]
                    )

                nop_count = 0

            previous = instruction

        if needs_tree_assemble:
            self.assemble_instructions_from_tree(root)
            return

        # We are now sure that we have enough space for all data, so we can assemble the EXTENDED_ARG instructions
        # duplicate of assemble_fast() with less safety checks, as we checked that stuff beforehand
        self.__raw_code.clear()
        for i, instruction in enumerate(self.__instructions):
            arg = instruction.get_arg()

            if instruction.opcode in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                arg -= 1

            if arg > 255:
                extend = arg // 256
                arg %= 256

                offset = 1
                while extend > 0:
                    iarg = extend % 256
                    extend //= 256

                    self.__raw_code[(i - offset) * 2 : (i - offset + 1) * 2] = bytes(
                        [Opcodes.EXTENDED_ARG, iarg]
                    )
                    offset += 1

            self.__raw_code += bytes([instruction.opcode, arg])

    def assemble_fast(self, instructions: typing.List[Instruction]):
        """
        Assembles the instruction list in FAST mode
        Removes some safety checks, and removes the dynamic assemble_instructions_from_tree() forwarding.
        Requires the linking of instructions to be LINEAR.

        :raises ValueError: if not enough space for EXTENDED_ARG's is available
        """

        self.__instructions = [
            instruction.update_owner(self, i, update_following=False)
            for i, instruction in enumerate(instructions)
        ]

        self.__raw_code.clear()
        for i, instruction in enumerate(self.__instructions):
            if instruction.opcode > 255:
                raise ValueError(f"invalid instruction at result level: {instruction}")

            arg = instruction.get_arg()

            if arg > 255:
                extend = arg // 256
                arg %= 256

                offset = 1
                while extend > 0:
                    iarg = extend % 256
                    extend //= 256

                    if self.__raw_code[(i - offset) * 2] != Opcodes.NOP:
                        raise ValueError(
                            f"Cannot assemble fast, not enough NOP's for instruction {instruction}"
                        )

                    self.__raw_code[(i - offset) * 2 : (i - offset + 1) * 2] = bytes(
                        [Opcodes.EXTENDED_ARG, iarg]
                    )
                    offset += 1

            if not (0 <= arg <= 255 and 0 <= instruction.opcode <= 255):
                print("error", instruction)

                print("----")

                for ins in instructions:
                    print(repr(ins))

                print("----")

            self.__raw_code += bytes([instruction.opcode, arg])

    def get_raw_code(self):
        if self.__instructions is not None:
            self.assemble_instructions()

        return self.__raw_code

    def set_raw_code(self, raw_code: bytearray):
        self.__raw_code = raw_code

        if self.__instructions is not None:
            self.decode_instructions()

    raw_code = property(get_raw_code, set_raw_code)

    def get_instructions(self):
        if self.__instructions is None:
            self.decode_instructions()

        return self.__instructions

    def set_instructions(self, instructions: typing.List[Instruction]):
        # Update the ownerships of the instructions, so they point to us now
        # todo: do we want to copy in some cases?
        self.__instructions = [
            instruction.update_owner(self, i)
            for i, instruction in enumerate(instructions)
        ]

    instructions = property(get_instructions, set_instructions)

    def allocate_shared_name(self, name: str) -> int:
        if name in self.shared_names:
            return self.shared_names.index(name)
        self.shared_names.append(name)
        return len(self.shared_names) - 1

    def allocate_shared_constant(self, value: object) -> int:
        if value in self.constants:
            return self.constants.index(value)
        self.constants.append(value)
        return len(self.constants) - 1

    def allocate_shared_variable_name(self, variable_name: str) -> int:
        if variable_name in self.shared_variable_names:
            return self.shared_variable_names.index(variable_name)
        self.shared_variable_names.append(variable_name)
        return len(self.shared_variable_names) - 1

    def allocate_shared_cell(self, name: str):
        if name in self.cell_variables:
            return self.cell_variables.index(name)
        self.cell_variables.append(name)
        return len(self.cell_variables) - 1

    def dump_info(self, file: str):
        data = {
            "instructions": [
                {
                    "opcode": instr.opcode,
                    "opname": instr.opname,
                    "arg": instr.arg,
                    "arg_value": repr(instr.arg_value),
                    "offset": instr.offset,
                }
                for instr in self.instructions
            ]
        }

        with open(file, mode="w") as f:
            simplejson.dump(data, f, indent="  ")


bytecodemanipulation.data_loader.init()
