import copy
import dis
import sys
import types
import typing
import simplejson

import bytecodemanipulation.assembler.util.tokenizer
from bytecodemanipulation.Opcodes import HAS_CELL_VARIABLE
from bytecodemanipulation.Opcodes import HAS_JUMP_BACKWARDS
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
import bytecodemanipulation.data_loader
from bytecodemanipulation.util import AbstractInstructionWalker


class LinearCodeConstraintViolationException(Exception):
    pass


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
        token: bytecodemanipulation.assembler.util.tokenizer.AbstractToken,
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
