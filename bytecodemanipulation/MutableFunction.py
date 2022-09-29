import dis
import types
import typing
import inspect
from bytecodemanipulation.Opcodes import (
    Opcodes,
    END_CONTROL_FLOW,
    OPCODE2NAME,
    OPNAME2CODE,
    HAS_NAME,
    HAS_CONST,
    HAS_LOCAL,
    HAS_JUMP_ABSOLUTE,
    HAS_JUMP_FORWARD,
    UNCONDITIONAL_JUMPS,
)


class LinearCodeConstraintViolationException(Exception):
    pass


class AbstractInstructionWalker:
    def visit(self, instruction: "Instruction"):
        raise NotImplementedError


class Instruction:
    @classmethod
    def _pair_instruction(cls, opcode: int | str) -> typing.Tuple[int, str]:
        if isinstance(opcode, int):
            return opcode, OPCODE2NAME[opcode]

        return OPNAME2CODE[opcode], opcode

    __slots__ = (
        "function",
        "offset",
        "opcode",
        "opname",
        "arg_value",
        "arg",
        "_next_instruction",
        "previous_instructions",
    )

    @classmethod
    def create(cls, *args, **kwargs):
        return cls(None, -1, *args, **kwargs)

    def __init__(
        self,
        function: typing.Optional["MutableFunction"],
        offset: int | None,
        opcode_or_name: int | str,
        arg_value: object = None,
        arg: int = None,
        _decode_next=True,
    ):
        self.function = function
        self.offset = offset
        self.opcode, self.opname = self._pair_instruction(opcode_or_name)
        self.arg_value = arg_value
        self.arg = arg

        if (
            self.arg is not None
            and self.arg_value is None
            and (_decode_next or not self.has_jump())
        ):
            self.change_arg(self.arg)
        elif self.arg_value is not None and self.arg is None:
            self.change_arg_value(self.arg_value)

        # Reference to the next instruction
        # Will raise an exception if changed and not using assemble_instructions_from_tree()
        self._next_instruction: typing.Optional[Instruction] = (
            None
            if function is None
            or offset is None
            or self.opcode in END_CONTROL_FLOW
            or not _decode_next
            else function.instructions[offset + 1]
        )

        self.previous_instructions: typing.List["Instruction"] | None = None

    def apply_visitor(
        self,
        visitor: AbstractInstructionWalker,
        visited: typing.Set["Instruction"] = None,
    ):
        if visited is None:
            visited = set()

        visitor.visit(self)

        if self.has_stop_flow():
            return

        self.next_instruction.apply_visitor(visitor, visited)

        if self.has_jump():
            typing.cast(Instruction, self.arg_value).apply_visitor(visitor, visited)

    def add_previous_instruction(self, instruction: "Instruction"):
        if self.previous_instructions is None:
            self.previous_instructions = [instruction]
        elif instruction not in self.previous_instructions:
            self.previous_instructions.append(instruction)

    def remove_previous_instruction(self, instruction: "Instruction"):
        if (
            self.previous_instructions is not None
            and instruction in self.previous_instructions
        ):
            self.previous_instructions.remove(instruction)

    def get_previous_instructions(self) -> typing.List["Instruction"]:
        if self.has_stop_flow():
            return []

        if self.previous_instructions is None:
            if self.function is None:
                raise ValueError(f"Instruction {self} is not bound!")

            self.function.prepare_previous_instructions()

            if self.previous_instructions is None:
                raise RuntimeError(f"Could not find previous instructions for {self}")

        return self.previous_instructions

    def set_next_instruction(self, instruction: typing.Optional["Instruction"]):
        if self._next_instruction is not None:
            self._next_instruction.remove_previous_instruction(self)

        self._next_instruction = instruction

        if instruction is not None:
            instruction.add_previous_instruction(self)

    def get_next_instruction(self) -> typing.Optional["Instruction"]:
        return self._next_instruction

    next_instruction = property(get_next_instruction, set_next_instruction)

    def __repr__(self):
        assert self.function is None or isinstance(self.function.function_name, str)
        assert isinstance(self.offset, int)
        assert isinstance(self.opcode, int)
        assert isinstance(self.arg, int) or self.arg is None
        assert self != self.arg_value

        return f"Instruction(function={self.function.function_name if self.function else '{Not Bound}'}, position={self.offset}, opcode={self.opcode}, opname={self.opname}, arg={self.arg}, arg_value={self.arg_value if not isinstance(self.arg_value, Instruction) else self.arg_value.repr_safe()}, has_next={self.next_instruction is not None})"

    def repr_safe(self):
        return f"Instruction(function={self.function.function_name if self.function else '{Not Bound}'}, position={self.offset}, opcode={self.opcode}, opname={self.opname}, arg={self.arg}, arg_value=..., has_next={self.next_instruction is not None})"

    def __eq__(self, other):
        if not isinstance(other, Instruction):
            return False

        return (
            self.opcode == other.opcode
            and (
                self.arg == other.arg
                if self.arg is not None and other.arg is not None
                else True
            )
            and (
                self.arg_value == other.arg_value
                if self.arg_value is not None and other.arg_value is not None
                else True
            )
        )

    def __hash__(self):
        return id(self)

    def get_arg(self):
        return 0 if self.arg is None else self.arg

    def change_opcode(self, opcode: int | str):
        self.opcode, self.opname = self._pair_instruction(opcode)
        # todo: what happens with the arg?

        self.next_instruction = (
            None
            if self.function is None
            or self.offset is None
            or self.opcode in END_CONTROL_FLOW
            or self.offset == -1
            else self.function.instructions[self.offset + 1]
        )

        if self.opcode == Opcodes.NOP:
            self.arg = 0
            self.arg_value = None

    def change_arg_value(self, value: object):
        self.arg_value = value

        if self.function is not None:
            if self.opcode in HAS_NAME:
                assert isinstance(value, str)
                self.arg = self.function.allocate_shared_name(value)
            elif self.opcode in HAS_CONST:
                self.arg = self.function.allocate_shared_constant(value)
            elif self.opcode in HAS_LOCAL:
                assert isinstance(value, str), (value, self.opname)
                self.arg = self.function.allocate_shared_variable_name(value)
            elif self.opcode in HAS_JUMP_ABSOLUTE:
                assert isinstance(value, Instruction), value
                self.arg = value.offset
            elif self.opcode in HAS_JUMP_FORWARD:
                assert isinstance(value, Instruction), value
                self.arg = value.offset - self.offset
        else:
            self.arg = None

    def change_arg(self, arg: int):
        self.arg = arg

        if self.function is not None:
            if self.opcode in HAS_NAME:
                self.arg_value = self.function.shared_names[arg]
            elif self.opcode in HAS_CONST:
                self.arg_value = self.function.constants[arg]
            elif self.opcode in HAS_LOCAL:
                self.arg_value = self.function.shared_variable_names[arg]
            elif self.opcode in HAS_JUMP_ABSOLUTE:
                self.arg_value = self.function.instructions[arg]
            elif self.opcode in HAS_JUMP_FORWARD and self.offset is not None:
                self.arg_value = self.function.instructions[arg + self.offset]
        else:
            self.arg_value = None

    def has_name(self):
        return self.opcode in HAS_NAME

    def has_constant(self):
        return self.opcode in HAS_CONST

    def has_local(self):
        return self.opcode in HAS_LOCAL

    def has_jump_absolute(self):
        return self.opcode in HAS_JUMP_ABSOLUTE

    def has_jump_forward(self):
        return self.opcode in HAS_JUMP_FORWARD

    def has_jump_backward(self):
        return False

    def has_jump(self):
        return (
            self.has_jump_absolute()
            or self.has_jump_forward()
            or self.has_jump_backward()
        )

    def has_unconditional_jump(self):
        return self.opcode in UNCONDITIONAL_JUMPS

    def has_stop_flow(self):
        return self.opcode in END_CONTROL_FLOW

    def update_owner(self, function: "MutableFunction", offset: int, update_following=True):
        previous_function = self.function

        self.function = function
        self.offset = offset

        # If previously the ownership was unset, and we have not fully referenced args, do it now!
        # todo: when previous owner was set, and arg is not None, we might need to de-ref the value
        #    and re-ref afterwards, so the value lives in the new owner
        if self.arg is not None and self.arg_value is None:
            self.change_arg(self.arg)
        elif self.arg_value is not None and self.arg is None:
            self.change_arg_value(self.arg_value)

        if update_following:
            self.next_instruction = (
                (None if previous_function != function else self.next_instruction)
                if function is None
                or offset is None
                or self.opcode in END_CONTROL_FLOW
                or offset == -1
                or offset + 1 >= len(function.instructions)
                else function.instructions[offset + 1]
            )

        return self

    def optimise_tree(self, visited: typing.Set["Instruction"] = None) -> "Instruction":
        """
        Optimises the instruction tree, removing NOP's and inlining unconditional jumps
        WARNING: this WILL invalidate the linearity of any instruction list, you MUST use assemble_instructions_from_tree()
        for inserting it back into the Function.

        Requires next_instruction's to be set, meaning it must be owned at some point by a function
        """

        if self.has_unconditional_jump():
            return self.arg_value.optimise_tree(visited)

        if visited is None:
            visited = set()

        if self.opcode == Opcodes.NOP and self.next_instruction is not None:
            return self.next_instruction.optimise_tree(visited)

        if self in visited:
            return self

        while self.next_instruction is not None:
            assert isinstance(self.next_instruction, Instruction)

            if self.next_instruction.opname == "NOP":
                self.next_instruction = self.next_instruction.next_instruction
                continue

            if self.next_instruction.opname in ("JUMP_ABSOLUTE", "JUMP_FORWARD"):
                self.next_instruction = self.next_instruction.arg_value
                continue

            break

        visited.add(self)

        if (
            self.next_instruction is not None
            and not self.has_stop_flow()
            and not self.has_unconditional_jump()
        ):
            self.next_instruction = self.next_instruction.optimise_tree(visited)

        if (
            self.has_jump_absolute()
            or self.has_jump_forward()
            or self.has_jump_backward()
        ) and self.arg_value is not None:
            assert isinstance(self.arg_value, Instruction)
            self.arg_value = self.arg_value.optimise_tree(visited)

        return self

    def trace_stack_position(
        self, stack_position: int
    ) -> typing.Iterator["Instruction"]:
        for instr in self.previous_instructions:
            yield from instr._trace_stack_position(stack_position, set())

    def _trace_stack_position(
        self, stack_position: int, yielded: typing.Set["Instruction"]
    ) -> typing.Iterator["Instruction"]:
        assert stack_position >= 0

        if self in yielded:
            return

        pushed, popped, additional_pos = self.get_stack_affect()

        if pushed > stack_position:
            yielded.add(self)
            yield self

            if additional_pos:
                for instr in self.previous_instructions:
                    yield from instr._trace_stack_position(additional_pos, yielded)

            return

        stack_position -= pushed
        stack_position += popped

        for instr in self.previous_instructions:
            yield from instr._trace_stack_position(stack_position, yielded)

        if additional_pos:
            for instr in self.previous_instructions:
                yield from instr._trace_stack_position(additional_pos, yielded)

    def trace_stack_position_use(
        self, stack_position: int
    ) -> typing.Iterator["Instruction"]:
        yield from self._trace_stack_position(stack_position, set())

    def _trace_stack_position_use(
        self, stack_position: int, yielded: typing.Set["Instruction"]
    ) -> typing.Iterator["Instruction"]:
        assert stack_position >= 0

        if self in yielded:
            return

        pushed, popped, additional_pos = self.get_stack_affect()

        if popped > stack_position:
            yielded.add(self)
            yield self

            if additional_pos:
                for instr in self.previous_instructions:
                    yield from instr._trace_stack_position(additional_pos, yielded)

            return

        stack_position -= popped
        stack_position += pushed

        for instr in self.previous_instructions:
            yield from instr._trace_stack_position(stack_position, yielded)

        if additional_pos:
            for instr in self.previous_instructions:
                yield from instr._trace_stack_position(additional_pos, yielded)

    def get_stack_affect(self) -> typing.Tuple[int, int, int | None]:
        if self.opcode in (Opcodes.NOP,):
            return 0, 0, None

        if self.opcode in (
            Opcodes.LOAD_CONST,
            Opcodes.LOAD_GLOBAL,
            Opcodes.LOAD_FAST,
            Opcodes.LOAD_DEREF,
        ):
            return 1, 0, None

        if self.opcode in (
            Opcodes.CALL_FUNCTION,
            Opcodes.CALL_METHOD,
            Opcodes.BUILD_TUPLE,
            Opcodes.BUILD_LIST,
            Opcodes.BUILD_SET,
            Opcodes.BUILD_SLICE,
        ):
            return 1, self.arg, None

        if self.opcode == Opcodes.BUILD_MAP:
            return 1, self.arg * 2, None

        if self.opcode == Opcodes.RETURN_VALUE:
            raise ValueError(self)

        if self.opcode in (
            Opcodes.COMPARE_OP,
            Opcodes.LIST_EXTEND,
            Opcodes.LIST_APPEND,
            Opcodes.SET_ADD,
            Opcodes.SET_UPDATE,
            Opcodes.DICT_UPDATE,
            Opcodes.DICT_MERGE,
        ):
            return 1, 2, None

        raise RuntimeError(self)


class MutableFunction:
    def __init__(self, target: types.FunctionType | types.MethodType):
        if isinstance(target, staticmethod):
            target = target.__func__

        self.target = target
        self.code_object: types.CodeType = target.__code__

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

    def create_code_obj(self) -> types.CodeType:
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
            bytes(self.lnotab),
            tuple(self.free_variables),
            tuple(self.cell_variables),
        )

    def reassign_to_function(self):
        self.target.__code__ = self.create_code_obj()

    def decode_instructions(self):
        if self.__instructions is not None:
            self.__instructions.clear()
        else:
            self.__instructions = []

        extra: int = 0
        for i in range(0, len(self.__raw_code), 2):
            opcode, arg = self.__raw_code[i : i + 2]

            if opcode == Opcodes.EXTENDED_ARG:
                extra = extra * 256 + arg
                self.__instructions.append(
                    Instruction(self, i // 2, "NOP", _decode_next=False)
                )

            else:
                arg += extra * 256
                extra = 0

                self.__instructions.append(
                    Instruction(self, i // 2, opcode, arg=arg, _decode_next=False)
                )

        for i, instruction in enumerate(self.instructions):
            instruction.update_owner(self, i)

        self.prepare_previous_instructions()

    def prepare_previous_instructions(self):
        for instruction in self.instructions:
            if instruction.has_stop_flow():
                continue

            instruction.next_instruction.add_previous_instruction(instruction)

            if instruction.has_jump():
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
        for i, instruction in enumerate(instructions):
            if (
                not instruction.has_stop_flow()
                and not instruction.has_unconditional_jump()
            ):
                try:
                    instruction.next_instruction = instructions[i + 1]
                except:
                    print(instruction)
                    raise

        self.assemble_fast(instructions)
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
                    print(instruction)

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
        for instruction in instructions:
            if instruction.next_instruction is None:
                continue

            if instruction.has_jump_absolute():
                instruction.arg = instruction.next_instruction.offset
            elif instruction.has_jump_forward():
                instruction.arg = (
                    instruction.next_instruction.offset - instruction.offset
                )
            elif instruction.has_jump_backward():
                instruction.arg = (
                    instruction.offset - instruction.next_instruction.offset
                )

    def insert_needed_jumps(self, instructions):
        # Check for unconditional jumps required
        for instruction in instructions[:]:
            if instruction.has_stop_flow():
                continue

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

            # If we visited it, we can skip
            if instruction in visited:
                continue

            # Walk over the instructions as long as we have not met them
            while instruction not in visited:
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
                assert instruction.next_instruction is not None, instruction

                instruction = instruction.next_instruction

        return instructions

    def assemble_instructions(self):

        # Check for linearity violations
        for i, instruction in enumerate(self.__instructions):
            if (
                instruction.next_instruction is not None
                and instruction.offset + 1 != instruction.next_instruction.offset
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

                    # And now, insert the "NOP"'s required after the previous for the things
                    for delta in range(missing):
                        nop = Instruction(self, previous.offset + delta + 1, "NOP")
                        nop.next_instruction = instruction
                        previous.next_instruction = nop
                        previous = nop

            previous = instruction

        if needs_tree_assemble:
            self.assemble_instructions_from_tree(root)
            return

        # We are now sure that we have enough space for all data, so we can assemble the EXTENDED_ARG instructions
        # duplicate of assemble_fast() with less safety checks, as we checked that stuff beforehand
        self.__raw_code.clear()
        for i, instruction in enumerate(self.__instructions):
            arg = instruction.get_arg()

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
