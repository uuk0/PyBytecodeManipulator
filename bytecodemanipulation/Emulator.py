import dis
import importlib
import opcode
import typing

from bytecodemanipulation.MutableCodeObject import MutableCodeObject
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.util import Opcodes, PY_VERSION


class StackOverflowException(Exception):
    pass


class StackUnderflowException(Exception):
    pass


class LocalVariableOutOfBoundsException(Exception):
    pass


class LocalVariableNameNotBoundException(Exception):
    pass


class GlobalNameIndexOutOfBoundsException(Exception):
    pass


class InvalidOpcodeException(Exception):
    pass


class InstructionExecutionException(Exception):
    pass


class ExecutionManager:
    INSTRUCTIONS: typing.List[
        typing.Tuple[
            typing.Tuple[int, int],
            typing.Optional[typing.Tuple[int, int]],
            int,
            "AbstractInstructionExecutor",
        ]
    ] = []
    MANAGERS: typing.List["ExecutionManager"] = []

    @classmethod
    def get_for_version(
        cls, version: typing.Tuple[int, int]
    ) -> typing.Optional["ExecutionManager"]:
        for manager in cls.MANAGERS:
            if manager.py_version == version:
                return manager

    def __init__(self, py_version: typing.Tuple[int, int]):
        self.py_version = py_version
        self.opcode2executor: typing.Dict[int, "AbstractInstructionExecutor"] = {}
        ExecutionManager.MANAGERS.append(self)

    def init(self):
        self.opcode2executor.clear()
        assert self.py_version is not None

        for start, end, opcode, executor in self.INSTRUCTIONS:
            assert start is not None
            if start <= self.py_version and (end is None or self.py_version <= end):
                self.opcode2executor[opcode] = executor

    def execute(self, target, *args, invoke_subcalls_via_emulator=False, **kwargs):
        env = ExecutionEnvironment(self)
        env.invoke_subcalls_via_emulator = invoke_subcalls_via_emulator
        patcher = MutableCodeObject.from_function(target)
        env.max_stack_size = patcher.max_stack_size
        env.local_variables = [None] * len(patcher.variable_names)
        env.local_variables[: len(args)] = args
        wrapper = BytecodePatchHelper(patcher)

        env.patcher = patcher

        while env.running:
            cp = env.cp
            instr = wrapper.instruction_listing[cp]

            if instr.opcode not in self.opcode2executor:
                raise InvalidOpcodeException(
                    f"Opcode {instr.opcode} ({instr.opname}) with arg {instr.arg} ({instr.argval}) is not valid in py version {self.py_version}"
                )

            executor = self.opcode2executor[instr.opcode]

            try:
                executor.invoke(instr, env)
            except:
                raise InstructionExecutionException(instr, executor)

            # print(instr, env.stack, env.local_variables)

            if env.cp == cp:
                env.cp += 1

        return env.return_value


class ExecutionEnvironment:
    def __init__(self, manager: ExecutionManager):
        self.manager = manager

        self.max_stack_size = -1
        self.stack = []
        self.local_variables = []

        self.patcher: typing.Optional[MutableCodeObject] = None
        self.invoke_subcalls_via_emulator = False

        self.cp = 0
        self.running = True
        self.return_value = None

    def pop(self, count: int = 1, position: int = -1, force_list=False):
        if len(self.stack) - count - (abs(position) - 1) < 0:
            raise StackUnderflowException(
                f"Could not pop {count} elements from position {position} from stack of size {len(self.stack)}"
            )

        if count == 1 and not force_list:
            return self.stack.pop(position)

        data = []
        for _ in range(count):
            data.append(self.stack.pop(position))

        return data

    def seek(self, offset: int = 0):
        if offset > 0:
            offset = -offset - 1

        if abs(offset) + 1 > len(self.stack):
            raise StackUnderflowException(
                f"Could not seek from position {-offset + 1}, as the stack size is only {len(self.stack)}"
            )

        return self.stack[offset]

    def push(self, value):
        if self.max_stack_size != -1 and len(self.stack) + 1 > self.max_stack_size:
            raise StackOverflowException(
                f"Could not push {value} into stack; max stack size of {self.max_stack_size} reached!"
            )

        self.stack.append(value)
        return self

    def push_to(self, value, index: int):
        if index > 0:
            index = -index - 1
        if self.max_stack_size != -1 and len(self.stack) + 1 == self.max_stack_size:
            raise StackOverflowException(
                f"Could not push {value} into stack; max stack size of {self.max_stack_size} reached!"
            )
        if abs(index) > len(self.stack):
            raise StackUnderflowException(
                f"Could not push into position {-index + 1}, as the current stack size is only {len(self.stack)}"
            )
        self.stack.insert(index, value)
        return self


PYTHON_3_6 = ExecutionManager((3, 6))
PYTHON_3_7 = ExecutionManager((3, 7))
PYTHON_3_8 = ExecutionManager((3, 8))
PYTHON_3_9 = ExecutionManager((3, 9))
PYTHON_3_10 = ExecutionManager((3, 10))
PYTHON_3_11 = ExecutionManager((3, 11))

CURRENT = ExecutionManager.get_for_version(PY_VERSION)


def register_opcode(
    opname: typing.Union[str, int],
    since: typing.Tuple[int, int] = (0, 0),
    until: typing.Tuple[int, int] = None,
):
    def annotate(cls):
        if isinstance(opname, str):
            # Only if the opcode is valid, register it
            if opname in dis.opmap:
                opcode = dis.opmap[opname]
                ExecutionManager.INSTRUCTIONS.append((since, until, opcode, cls()))
            else:
                print("skipping opcode", opname)
        else:
            ExecutionManager.INSTRUCTIONS.append((since, until, opname, cls()))

        return cls

    return annotate


class AbstractInstructionExecutor:
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        raise NotImplementedError


@register_opcode("NOP")
@register_opcode("RESUME", (3, 11))
@register_opcode("COPY_FREE_VARS", (3, 11))
class NOPExecutor(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        pass


@register_opcode("POP_TOP")
class OpcodePopTop(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.pop()


@register_opcode("ROT_TWO")
class OpcodeRotTwo(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push_to(env.pop(), 1)


@register_opcode("ROT_THREE")
class OpcodeRotThree(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push_to(env.pop(), 2)


@register_opcode("ROT_FOUR", (3, 8))
class OpcodeRotThree(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push_to(env.pop(), 3)


@register_opcode("DUP_TOP", (3, 2))
class OpcodeDupTop(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(env.seek())


@register_opcode("DUP_TOP_TWO", (3, 2))
class OpcodeDupTopTwo(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(env.seek())
        env.push_to(env.seek(2), 1)


@register_opcode("RETURN_VALUE")
class OpcodeReturnValue(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.return_value = env.pop()
        env.running = False


@register_opcode("LOAD_CONST")
class OpcodeLoadConst(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(env.patcher.constants[instr.arg])


@register_opcode("LOAD_FAST")
class OpcodeLoadFast(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(env.local_variables[instr.arg])


@register_opcode("STORE_FAST")
class OpcodeStoreFast(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.local_variables[instr.arg] = env.pop()


@register_opcode("LOAD_GLOBAL")
class OpcodeLoadGlobal(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        try:
            env.push(env.patcher.target.__globals__[instr.argval])
        except KeyError:
            try:
                env.push(globals()[instr.argval])
            except KeyError:
                env.push(eval(instr.argval))


@register_opcode("STORE_GLOBAL")
class OpcodeStoreGlobal(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.patcher.target.__globals__[instr.argval] = env.pop()


@register_opcode("POP_JUMP_IF_TRUE", (3, 1))
class OpcodePopJumpIfTrue(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        value = env.pop()
        if value is True:
            env.cp = instr.arg


@register_opcode("POP_JUMP_IF_FALSE", (3, 1))
class OpcodePopJumpIfFalse(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        value = env.pop()
        if value is False:
            env.cp = instr.arg


@register_opcode("COMPARE_OP")
class OpcodeCompareOp(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        right, left = env.pop(2)
        operation = opcode.cmp_op[instr.arg]
        env.push(eval(f"a {operation} b", {"a": left, "b": right}))


@register_opcode("GET_ITER")
class OpcodeGetIter(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(iter(env.pop()))


@register_opcode("FOR_ITER")
class OpcodeForIter(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        iterator = env.seek()
        try:
            env.push(next(iterator))
        except StopIteration:
            env.pop()
            env.cp += instr.arg + 1


@register_opcode("JUMP_ABSOLUTE")
@register_opcode("JUMP_NO_INTERRUPT", (3, 11))
class OpcodeJumpAbsolute(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.cp = instr.arg


@register_opcode("JUMP_FORWARD")
class OpcodeJumpForward(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.cp += instr.arg


@register_opcode("BINARY_OP", (3, 11))
class OpcodeBinaryOp(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        name, op = dis._nb_ops[instr.arg]

        if op == "+=":
            a, b = env.pop(2)
            env.push(a + b)
            return

        if op == "-=":
            a, b = env.pop(2)
            env.push(b - a)
            return

        if op == "*=":
            a, b = env.pop(2)
            env.push(b * a)
            return

        if op == "/=":
            a, b = env.pop(2)
            env.push(b / a)
            return

        if op == "//=":
            a, b = env.pop(2)
            env.push(b // a)
            return

        if op == "%=":
            a, b = env.pop(2)
            env.push(b % a)
            return

        if op == "&=":
            a, b = env.pop(2)
            env.push(b & a)
            return

        if op == "|=":
            a, b = env.pop(2)
            env.push(b | a)
            return

        if op == "^=":
            a, b = env.pop(2)
            env.push(b ^ a)
            return

        if op == "@=":
            a, b = env.pop(2)
            env.push(b @ a)
            return

        raise NotImplementedError(instr, op)


@register_opcode("INPLACE_SUBTRACT", (0, 0), (3, 10))
class OpcodeInplaceSubtract(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        a, b = env.pop(2)
        env.push(b - a)


@register_opcode("INPLACE_ADD", (0, 0), (3, 10))
class OpcodeInplaceAdd(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        a, b = env.pop(2)
        env.push(b + a)


@register_opcode("CALL_NO_KW", (3, 11))
@register_opcode("CALL_FUNCTION", (0, 0), (3, 10))
class OpcodeCallNoKw(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        args = env.pop(instr.arg, force_list=True)

        method = env.pop()

        if env.invoke_subcalls_via_emulator and hasattr(method, "__code__"):
            return env.manager.execute(method, *reversed(args))

        # todo: add option to also call using the emulator if possible
        env.push(method(*reversed(args)))


@register_opcode("CALL_METHOD", (0, 0), (3, 10))
class OpcodeCallMethod(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        args = env.pop(instr.arg, force_list=True)

        method = env.pop()

        if env.invoke_subcalls_via_emulator and hasattr(method, "__code__"):
            return env.manager.execute(method, *reversed(args))

        if not callable(method):
            raise ValueError(f"method on stack was not callable; tried to invoke {method} with args {args}")

        # todo: add option to also call using the emulator if possible
        env.push(method(*reversed(args)))


@register_opcode("IMPORT_NAME")
class OpcodeImportName(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(importlib.import_module(instr.argval))


@register_opcode("IMPORT_FROM")
@register_opcode("LOAD_ATTR")
class OpcodeImportFrom(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(getattr(env.pop(), instr.argval))


@register_opcode("BUILD_LIST")
class OpcodeBuildList(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(list(reversed(env.pop() for _ in range(instr.arg))))


@register_opcode("BUILD_TUPLE")
class OpcodeBuildTuple(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(tuple(reversed(env.pop() for _ in range(instr.arg))))


@register_opcode("BUILD_SET")
class OpcodeBuildSet(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push({env.pop() for _ in range(instr.arg)})


@register_opcode("BUILD_DICT")
class OpcodeBuildSet(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        items = reversed(env.pop() for _ in range(2 * instr.arg))
        env.push({next(items): next(items) for _ in range(instr.arg)})


@register_opcode("BUILD_STRING")
class OpcodeBuildString(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push("".join(*reversed(env.pop() for _ in range(instr.arg))))


@register_opcode("LIST_TO_TUPLE")
class OpcodeListToTuple(AbstractInstructionExecutor):
    @classmethod
    def invoke(cls, instr: dis.Instruction, env: ExecutionEnvironment):
        env.push(tuple(env.pop()))


for manager in ExecutionManager.MANAGERS:
    manager.init()
