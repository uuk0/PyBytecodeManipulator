import dis
import sys
import typing

import bytecodemanipulation.assembler
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.Opcodes import END_CONTROL_FLOW
from bytecodemanipulation.Opcodes import HAS_CELL_VARIABLE
from bytecodemanipulation.Opcodes import HAS_CONST
from bytecodemanipulation.Opcodes import HAS_JUMP_ABSOLUTE
from bytecodemanipulation.Opcodes import HAS_JUMP_BACKWARDS
from bytecodemanipulation.Opcodes import HAS_JUMP_FORWARD
from bytecodemanipulation.Opcodes import HAS_LOCAL
from bytecodemanipulation.Opcodes import HAS_NAME
from bytecodemanipulation.Opcodes import OPCODE2NAME
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Opcodes import OPNAME2CODE
from bytecodemanipulation.Opcodes import UNCONDITIONAL_JUMPS
from bytecodemanipulation.util import AbstractInstructionWalker


if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction


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
        "source_location",
    )

    @classmethod
    def create(cls, *args, **kwargs):
        return cls(None, -1, *args, **kwargs)

    @classmethod
    def create_with_token(
        cls,
        token: AbstractToken,
        function: typing.Optional["MutableFunction"],
        offset: int | None,
        opcode_or_name: int | str,
        arg_value: object = None,
        arg: int = None,
        _decode_next=True,
    ) -> "Instruction":
        raise NotImplementedError("not bound!")

    def __init__(
        self,
        function: typing.Optional["MutableFunction"],
        offset: int | None,
        opcode_or_name: int | str,
        arg_value: object = None,
        arg: int = None,
        _decode_next=True,
        pos_info=None,
    ):
        self.function = function
        self.offset = offset
        self.opcode, self.opname = self._pair_instruction(opcode_or_name)
        self.arg_value = arg_value
        self.arg = arg
        self.source_location = pos_info

        if (
            self.arg is not None
            and self.arg_value is None
            and (_decode_next or not self.has_jump())
        ):
            self.change_arg(self.arg)
        elif (
            self.arg_value is not None or self.opcode == Opcodes.LOAD_CONST
        ) and self.arg is None:
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

    def copy(self, owner: "MutableFunction" = None) -> "Instruction":
        instance = type(self)(
            self.function,
            self.offset,
            self.opcode,
            self.arg_value
            if self.arg_value is not None or self.opcode == Opcodes.LOAD_CONST
            else self.arg,
        )

        if owner:
            instance.update_owner(owner, -1, force_change_arg_index=True)

        return instance

    def apply_visitor(
        self,
        visitor: AbstractInstructionWalker,
        visited: typing.Set["Instruction"] = None,
    ):
        if visited is None:
            visited = set()

        if self in visited:
            return

        visited.add(self)

        visitor.visit(self)

        if self.has_stop_flow():
            return

        if self.next_instruction is not None and self.next_instruction != self:
            self.next_instruction.apply_visitor(visitor, visited)

        if self.has_jump() and isinstance(self.arg_value, Instruction):
            typing.cast(Instruction, self.arg_value).apply_visitor(visitor, visited)

    def apply_value_visitor(
        self,
        callback: typing.Callable[
            ["Instruction", typing.Any | None, typing.Any | None], typing.Any
        ],
        visited: typing.Dict["Instruction", typing.Any] = None,
    ) -> typing.Any:
        if visited is None:
            visited = {}

        elif self in visited:
            return visited[self]

        visited[self] = None

        if self.has_stop_flow():
            return callback(self, None, None)

        if self.has_jump() and isinstance(self.arg_value, Instruction):
            return callback(
                self,
                self.next_instruction.apply_value_visitor(callback, visited),
                self.arg_value.apply_value_visitor(callback, visited),
            )

        if self.next_instruction is not None:
            return callback(
                self, self.next_instruction.apply_value_visitor(callback, visited), None
            )

        return callback(self, None, None)

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
                raise ValueError(
                    f"Instruction {self} is not bound to a MutableFunction object, making retrieving the previous instruction list impossible!!"
                )

            self.function.prepare_previous_instructions()

            if self.previous_instructions is None:
                raise RuntimeError(
                    f"Could not find previous instructions for {self}. This should NOT happen, as we asked the method which MUST yield results. (See MutableFunction.prepare_previous_instructions())"
                )

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
        if id(self) == id(self.arg_value):
            return self.repr_safe() + "@self_arg_value"

        return f"Instruction(function={self.function.function_name if self.function else '{Not Bound}'}, position={self.offset}, opcode={self.opcode}, opname={self.opname}, arg={self.arg}, arg_value={self.arg_value.repr_safe() if self.arg_value is not None and isinstance(self.arg_value, Instruction) else self.arg_value}, has_next={self.next_instruction is not None})"

    def repr_safe(self):
        return f"Instruction(function={self.function.function_name if self.function else '{Not Bound}'}, position={self.offset}, opcode={self.opcode}, opname={self.opname}, arg={self.arg}, arg_value=..., has_next={self.next_instruction is not None})"

    def __eq__(self, other):
        if not isinstance(other, Instruction):
            return False

        return (
            self.opcode == other.opcode
            and (
                self.offset == other.offset
                or self.offset is None
                or other.offset is None
            )
            and (
                (self.arg_value == other.arg_value)
                if not isinstance(self.arg_value, Instruction)
                else (id(self.arg_value) == id(other.arg_value))
                if self.arg_value is not None and other.arg_value is not None
                else True
            )
        )

    def lossy_eq(self, other: "Instruction") -> bool:
        if not isinstance(other, Instruction):
            return False

        return self.opcode == other.opcode and (
            (
                (self.arg_value == other.arg_value)
                if not isinstance(self.arg_value, Instruction)
                else self.arg_value.lossy_eq(other.arg_value)
            )
            if (self.arg_value is not None and other.arg_value is not None)
            or self.opcode == Opcodes.LOAD_CONST
            else True
        )

    def __hash__(self):
        return id(self)

    def get_arg(self):
        return 0 if self.arg is None else self.arg

    def change_opcode(self, opcode: int | str, arg_value=None, update_next=True):
        self.opcode, self.opname = self._pair_instruction(opcode)
        # todo: what happens with the arg?

        if update_next:
            self.next_instruction = (
                None
                if self.function is None
                or self.offset is None
                or self.opcode in END_CONTROL_FLOW
                or self.offset == -1
                else self.function.instructions[self.offset + 1]
            )

        if self.opcode < dis.HAVE_ARGUMENT:
            self.arg = 0
            self.arg_value = None

        if arg_value:
            self.change_arg_value(arg_value)

        return self

    def change_arg_value(self, value: object):
        self.arg_value = value

        if self.function is not None:
            if self.opcode in HAS_NAME:
                assert isinstance(value, str)
                self.arg = self.function.allocate_shared_name(value)
            elif self.opcode in HAS_CELL_VARIABLE:
                assert isinstance(value, str)
                self.arg = self.function.allocate_shared_cell(value)
            elif self.opcode in HAS_CONST:
                self.arg = self.function.allocate_shared_constant(value)
            elif self.opcode in HAS_LOCAL:
                assert isinstance(value, str), (value, self.opname)
                self.arg = self.function.allocate_shared_variable_name(value)
            elif self.opcode in HAS_JUMP_ABSOLUTE:
                if isinstance(value, Instruction):
                    self.arg = value.offset
            elif self.opcode == Opcodes.FOR_ITER:
                if isinstance(value, Instruction):
                    self.arg = value.offset - self.offset
            elif self.opcode in HAS_JUMP_FORWARD:
                assert isinstance(value, Instruction), value
                self.arg = value.offset - self.offset
        else:
            self.arg = None

    def change_arg(self, arg: int):
        self.arg = arg

        if self.function is not None:
            try:
                flag = False
                if sys.version_info.minor >= 11:
                    if self.opcode == Opcodes.LOAD_GLOBAL:
                        self.arg_value = self.function.shared_names[arg >> 1]
                        flag = True

                if flag:
                    pass
                elif self.opcode in HAS_NAME:
                    self.arg_value = self.function.shared_names[arg]
                elif self.opcode in HAS_CELL_VARIABLE:
                    self.arg_value = self.function.cell_variables[arg]
                elif self.opcode in HAS_CONST:
                    self.arg_value = self.function.constants[arg]
                elif self.opcode in HAS_LOCAL:
                    self.arg_value = self.function.shared_variable_names[arg]
                elif self.opcode in HAS_JUMP_ABSOLUTE:
                    self.arg_value = self.function.instructions[arg]
                elif self.opcode in (Opcodes.FOR_ITER, Opcodes.SETUP_FINALLY):
                    self.arg_value = self.function.instructions[arg + self.offset]
                elif self.opcode in HAS_JUMP_FORWARD and self.offset is not None:
                    self.arg_value = self.function.instructions[arg + self.offset]
            except:
                print(
                    self.opname,
                    arg,
                    self.function.shared_names,
                    self.function.constants,
                    self.function.shared_variable_names,
                )
                raise
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
        return self.opcode in HAS_JUMP_BACKWARDS

    def has_cell_variable(self):
        return self.opcode in HAS_CELL_VARIABLE

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

    def update_owner(
        self,
        function: "MutableFunction",
        offset: int,
        update_following=True,
        force_change_arg_index=False,
    ):
        previous_function = self.function

        self.function = function
        self.offset = offset

        # If previously the ownership was unset, and we have not fully referenced args, do it now!
        # todo: when previous owner was set, and arg is not None, we might need to de-ref the value
        #    and re-ref afterwards, so the value lives in the new owner
        if (
            self.arg is not None
            and self.arg_value is None
            and (not force_change_arg_index or self.opcode != Opcodes.LOAD_CONST)
        ):
            self.change_arg(self.arg)
        elif (self.arg_value is not None or self.opcode == Opcodes.LOAD_CONST) and (
            self.arg is None or force_change_arg_index
        ):
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

        if self in visited:
            return self

        visited.add(self)

        if self.opcode == Opcodes.NOP and self.next_instruction is not None:
            return self.next_instruction.optimise_tree(visited)

        while self.next_instruction is not None:
            assert isinstance(self.next_instruction, Instruction)

            if self.next_instruction.opname == "NOP":
                self.next_instruction = self.next_instruction.next_instruction
                continue

            if self.next_instruction.opname in ("JUMP_ABSOLUTE", "JUMP_FORWARD"):
                self.next_instruction = self.next_instruction.arg_value
                continue

            break

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
            self.change_arg_value(self.arg_value.optimise_tree(visited))

        return self

    def trace_variable_set(
        self, name: str, visited: typing.Set[str] = None
    ) -> typing.Iterator["Instruction"]:
        if visited and self in visited:
            return

        if self.opcode == Opcodes.STORE_FAST and self.arg_value == name:
            yield self
            return

        if self.opcode == Opcodes.DELETE_FAST:
            return

        if visited is None:
            visited = {self}

        if self.previous_instructions is None:
            return

        for prev in self.previous_instructions:
            yield from prev.trace_variable_set(name, visited)

    def trace_stack_position(
        self, stack_position: int
    ) -> typing.Iterator["Instruction"]:
        for instr in self.get_priorities_previous():
            yield from instr._trace_stack_position(stack_position, set(), self)

    def get_priorities_previous(self) -> typing.List["Instruction"]:
        if not self.previous_instructions:
            return []

        real_previous = [
            instr
            for instr in self.previous_instructions
            if instr.next_instruction == self
        ]
        unreal_previous = [
            instr
            for instr in self.previous_instructions
            if instr.next_instruction != self
        ]
        highest = None

        for e in real_previous:
            if e.offset == self.offset - 1 or e.opcode == Opcodes.SETUP_FINALLY:
                highest = e

        if not highest:
            return real_previous + unreal_previous

        return [highest] + [e for e in real_previous if e != highest] + unreal_previous

    def trace_normalized_stack_position(
        self, stack_position: int
    ) -> typing.Optional["Instruction"]:
        target = next(self.trace_stack_position(stack_position))

        if target.opcode == Opcodes.DUP_TOP:
            return target.trace_normalized_stack_position(0)

        if target.opcode == Opcodes.LOAD_FAST:
            try:
                variable_set = next(
                    target.trace_variable_set(typing.cast(str, target.arg_value))
                )
            except StopIteration:
                return target

            return variable_set.trace_normalized_stack_position(0)

        return target

    def _trace_stack_position(
        self,
        stack_position: int,
        yielded: typing.Set["Instruction"],
        previous_instr: "Instruction" = None,
    ) -> typing.Iterator["Instruction"]:
        assert stack_position >= 0

        if self in yielded:
            return

        if self.has_unconditional_jump():
            pushed, popped, additional_pos = 0, 0, None
        elif self.opcode == Opcodes.SETUP_FINALLY and previous_instr == self.arg_value:
            pushed, popped, additional_pos = 3, 0, None
        elif self.opcode in (
            Opcodes.JUMP_IF_TRUE_OR_POP,
            Opcodes.JUMP_IF_FALSE_OR_POP,
        ):
            if self.arg_value == previous_instr:
                pushed, popped, additional_pos = 0, 0, None
            else:
                pushed, popped, additional_pos = 0, 1, None
        else:
            pushed, popped, additional_pos = self.get_stack_affect()

        # print(self, stack_position, (pushed, popped, additional_pos), self.arg_value, previous_instr)

        if pushed > stack_position:
            yielded.add(self)
            # print("hit")
            yield self
            # print("cont")

            if additional_pos:
                for instr in self.get_priorities_previous():
                    yield from instr._trace_stack_position(
                        additional_pos, yielded, self
                    )

            return

        stack_position -= pushed
        stack_position += popped

        yielded.add(self)

        for instr in self.get_priorities_previous():
            try:
                yield from instr._trace_stack_position(stack_position, yielded, self)
            except:
                # print(self, instr)
                raise

        if additional_pos:
            for instr in self.get_priorities_previous():
                yield from instr._trace_stack_position(additional_pos, yielded, self)

    def trace_stack_position_use(
        self, stack_position: int
    ) -> typing.Iterator["Instruction"]:
        # print(self, 0)

        if not self.has_stop_flow():
            yield from self.next_instruction._trace_stack_position_use(
                stack_position, set()
            )

        if self.has_jump():
            yield from typing.cast(
                Instruction, self.arg_value
            )._trace_stack_position_use(stack_position, set())

    def _trace_stack_position_use(
        self, stack_position: int, yielded: typing.Set["Instruction"]
    ) -> typing.Iterator["Instruction"]:
        assert stack_position >= 0

        if self in yielded:
            return

        yielded.add(self)

        pushed, popped, additional_pos = self.get_stack_affect()

        if popped > stack_position:
            yielded.add(self)
            yield self

            if additional_pos:
                yield from self.next_instruction._trace_stack_position_use(
                    additional_pos, yielded
                )

            return

        stack_position -= popped
        stack_position += pushed

        if not self.has_stop_flow():
            yield from self.next_instruction._trace_stack_position_use(
                stack_position, yielded
            )

        if self.has_jump():
            yield from typing.cast(
                Instruction, self.arg_value
            )._trace_stack_position_use(stack_position, yielded)

        if additional_pos:
            yield from self.next_instruction._trace_stack_position_use(
                additional_pos, yielded
            )

    def get_stack_affect(self) -> typing.Tuple[int, int, int | None]:
        # pushed, popped, additional
        if self.opcode in (
            Opcodes.NOP,
            Opcodes.POP_BLOCK,
            Opcodes.POP_EXCEPT,
            Opcodes.SETUP_FINALLY,
            Opcodes.GEN_START,
            Opcodes.JUMP_ABSOLUTE,
            Opcodes.BYTECODE_LABEL,
            Opcodes.JUMP_FORWARD,
            Opcodes.RERAISE,
            # Opcodes.CACHE,
            # Opcodes.PRECALL,
            # Opcodes.RESUME,
        ):
            return 0, 0, None

        if self.opcode == Opcodes.DUP_TOP:
            return 2, 1, None

        if self.opcode == Opcodes.GET_ITER:
            return 1, 0, None

        if self.opcode == Opcodes.FOR_ITER:
            return 1, 1, None

        if self.opcode == Opcodes.BUILD_CONST_KEY_MAP:
            return 1, self.arg + 1, None

        if self.opcode in (
            Opcodes.LOAD_CONST,
            Opcodes.LOAD_GLOBAL,
            Opcodes.LOAD_FAST,
            Opcodes.LOAD_DEREF,
            Opcodes.LOAD_CLOSURE,
            Opcodes.LOAD_BUILD_CLASS,
            Opcodes.LOAD_ASSERTION_ERROR,
            Opcodes.LOAD_NAME,
        ):
            return 1, 0, None

        if self.opcode in (
            Opcodes.BUILD_TUPLE,
            Opcodes.BUILD_LIST,
            Opcodes.BUILD_SET,
            Opcodes.BUILD_SLICE,
            Opcodes.BUILD_STRING,
        ):
            return 1, self.arg, None

        if self.opcode in (Opcodes.ROT_TWO,):
            return 2, 2, None

        if self.opcode in (Opcodes.FORMAT_VALUE,):
            return 1, (2 if (self.arg & 0x04) == 0x04 else 1), None

        if self.opcode in (
            Opcodes.CALL_FUNCTION,
            Opcodes.CALL_METHOD,
            Opcodes.CALL_FUNCTION_KW,
            # Opcodes.CALL,
        ):
            return 1, self.arg + 1, None

        if self.opcode in (Opcodes.CALL_FUNCTION_EX,):
            count = 2

            if self.arg & 0x01:
                count += 1

            return 1, count, None

        if self.opcode == Opcodes.BUILD_MAP:
            return 1, self.arg * 2, None

        if self.opcode in (
            Opcodes.COMPARE_OP,
            Opcodes.IS_OP,
            Opcodes.BINARY_SUBSCR,
            Opcodes.CONTAINS_OP,
            Opcodes.LIST_EXTEND,
            Opcodes.LIST_APPEND,
            Opcodes.SET_ADD,
            Opcodes.SET_UPDATE,
            Opcodes.DICT_UPDATE,
            Opcodes.DICT_MERGE,
            Opcodes.BINARY_FLOOR_DIVIDE,
            Opcodes.BINARY_ADD,
            Opcodes.INPLACE_ADD,
            Opcodes.BINARY_SUBTRACT,
            Opcodes.BINARY_MULTIPLY,
            Opcodes.BINARY_TRUE_DIVIDE,
            Opcodes.BINARY_FLOOR_DIVIDE,
            Opcodes.BINARY_MODULO,
            Opcodes.BINARY_XOR,
            Opcodes.BINARY_AND,
            Opcodes.BINARY_OR,
            Opcodes.BINARY_POWER,
            Opcodes.INPLACE_SUBTRACT,
            Opcodes.IMPORT_NAME,
            Opcodes.YIELD_FROM,
        ):
            return 1, 2, None

        if self.opcode in (
            Opcodes.LOAD_ATTR,
            Opcodes.LOAD_METHOD,
            Opcodes.GET_AWAITABLE,
            Opcodes.LIST_TO_TUPLE,
            Opcodes.IMPORT_FROM,
            Opcodes.UNARY_NEGATIVE,
            Opcodes.YIELD_VALUE,
            Opcodes.GET_YIELD_FROM_ITER,
            Opcodes.UNARY_NOT,
            Opcodes.UNARY_NEGATIVE,
            Opcodes.UNARY_INVERT,
            Opcodes.UNARY_POSITIVE,
            Opcodes.STATIC_ATTRIBUTE_ACCESS,
        ):
            return 1, 1, None

        if self.opcode in (Opcodes.STORE_ATTR,):
            return 2, 0, None

        if self.opcode in (
            Opcodes.POP_TOP,
            Opcodes.POP_JUMP_IF_TRUE,
            Opcodes.POP_JUMP_IF_FALSE,
            Opcodes.STORE_FAST,
            Opcodes.STORE_NAME,
            Opcodes.STORE_DEREF,
            Opcodes.STORE_GLOBAL,
            Opcodes.RETURN_VALUE,
            Opcodes.JUMP_IF_TRUE_OR_POP,
        ):
            return 0, 1, None

        if self.opcode == Opcodes.UNPACK_SEQUENCE:
            return self.arg, 1, None

        if self.opcode == Opcodes.JUMP_IF_NOT_EXC_MATCH:
            return 0, 2, None

        if self.opcode == Opcodes.MAKE_FUNCTION:
            return 1, 2 + self.arg.bit_count(), None

        if self.opcode == Opcodes.RAISE_VARARGS:
            return 0, self.arg, None

        if self.opcode == Opcodes.DUP_TOP_TWO:
            return 2, 4, None

        if self.opcode == Opcodes.ROT_THREE:
            return 3, 3, None

        raise RuntimeError(self)

    def special_stack_affect_when_followed_by(self, instr: "Instruction") -> int:
        if self.opcode == Opcodes.FOR_ITER and instr == self.arg_value:
            return -2

        if self.opcode == Opcodes.JUMP_IF_TRUE_OR_POP and instr == self.arg_value:
            return -1

        return 0

    def insert_after(self, *instructions: "Instruction" | typing.List["Instruction"]):
        if not instructions:
            return self

        if isinstance(instructions[0], (list, tuple)):
            if len(instructions) > 1:
                raise ValueError

            instructions = instructions[0]

        if len(instructions) == 0:
            return self

        instructions[0].next_instruction = self.next_instruction
        self.next_instruction = instructions[0]

        if len(instructions) > 1:
            instructions[0].insert_after(instructions[1:])

        return self