import dis
import itertools
import types
import typing

from bytecodemanipulation import Opcodes
from bytecodemanipulation.MutableCodeObject import createInstruction
from bytecodemanipulation.MutableCodeObject import MutableCodeObject


class BoundInstruction:
    __slots__ = ("underlying", "real_bound", "offset_bound")

    def __init__(self, underlying: dis.Instruction):
        self.underlying = underlying
        self.real_bound = set()
        self.offset_bound = set()

    @property
    def opname(self): return self.underlying.opname

    @property
    def opcode(self): return self.underlying.opcode

    @property
    def arg(self): return self.underlying.arg

    @property
    def argval(self): return self.underlying.argval

    @property
    def argrepr(self): return self.underlying.argrepr

    @property
    def offset(self): return self.underlying.offset

    @property
    def starts_line(self): return self.underlying.starts_line

    @property
    def is_jump_target(self): return self.underlying.is_jump_target


class BytecodeBuilder:
    """
    Util class for manipulation of MutableCodeObject's in a more safe way,
    making sure that jumps are resolved correctly, and EXTENDED_ARG opcodes are
    omitted correctly as needed
    """

    @classmethod
    def from_method_instance(cls, method: types.FunctionType):
        return cls.from_mutable_code_object(MutableCodeObject.from_function(method))

    @classmethod
    def from_mutable_code_object(cls, obj: MutableCodeObject):
        return cls.from_instruction_list(obj.get_instruction_list(), obj)

    @classmethod
    def from_instruction_list(cls, instructions: typing.List[dis.Instruction], mutable: MutableCodeObject):
        instance = cls(list(filter(lambda e: e.opcode != Opcodes.EXTENDED_ARG, instructions)), mutable)
        instance.stabilize_jumps()
        return instance

    @classmethod
    def empty(cls):
        mutable = MutableCodeObject()
        return cls([], mutable)

    def __init__(self, instructions: typing.List[dis.Instruction], mutable: MutableCodeObject):
        self.instructions: typing.List[typing.Union[dis.Instruction, BoundInstruction]] = instructions
        self.patcher = mutable

    def stabilize_jumps(self):
        self.instructions = list(map(lambda e: e if isinstance(e, dis.Instruction) else e.underlying, self.instructions))

        for index, instruction in enumerate(self.instructions):
            instruction: dis.Instruction

            if instruction.opcode in dis.hasjrel:
                target = index + instruction.arg
                self.create_bound_instruction_body(target).offset_bound.add(index)

            elif instruction.opcode in dis.hasjabs:
                self.create_bound_instruction_body(instruction.arg).real_bound.add(index)

    def assemble(self):
        code_string = bytearray()
        instructions = self.instructions.copy()

        from bytecodemanipulation.TransformationHelper import rebind_instruction_from_insert

        new_instructions = []

        from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

        helper = BytecodePatchHelper(self.patcher)
        skipped = 0

        for index, instr in enumerate(instructions):
            if instr.opname == "EXTENDED_ARG":
                skipped += 1
                continue

            if instr.arg is not None and instr.arg >= 256:
                if instr.arg >= 256 * 256:
                    if instr.arg >= 256 * 256 * 256:
                        data = instr.arg.to_bytes(4, "big", signed=False)
                    else:
                        data = instr.arg.to_bytes(3, "big", signed=False)
                else:
                    data = instr.arg.to_bytes(2, "big", signed=False)

                for delta, e in enumerate(data[:-1]):
                    new_instructions.append(
                        (
                            dis.Instruction(
                                "EXTENDED_ARG",
                                144,
                                e,
                                e,
                                "",
                                index - (len(data) - delta),
                                None,
                                False,
                            )
                        )
                    )

                if len(data) != skipped + 1:
                    if len(data) > skipped + 1:
                        helper.insertRegion(index, [createInstruction("EXTENDED_ARG") for _ in range(len(data) - skipped - 1)])
                        for i, instr2 in enumerate(new_instructions):
                            new_instructions[i] = rebind_instruction_from_insert(instr2, index, len(data) - skipped - 1)

                        for i, instr2 in itertools.dropwhile(lambda a: a[0] <= index, enumerate(instructions)):
                            instructions[i] = rebind_instruction_from_insert(instr2, index, len(data) - skipped - 1)

                    else:
                        # todo: implement instruction offset remap
                        raise NotImplementedError(data, skipped)

            if skipped:
                skipped = 0

            new_instructions.append(instr)

        for instr in new_instructions:
            try:
                code_string.append(instr.opcode)

                if instr.arg is not None:
                    code_string.append(instr.arg % 256)
                else:
                    code_string.append(0)

            except:
                print(instr)
                raise

        return code_string

    def get_instr(self, index: int):
        instr = self.instructions[index]

        if isinstance(instr, BoundInstruction):
            return instr.underlying
        return instr

    def create_bound_instruction_body(self, position: int) -> BoundInstruction:
        base = self.instructions[position]

        if isinstance(base, BoundInstruction):
            return base

        base = BoundInstruction(base)
        self.instructions[position] = base
        return base

    def add(self, instruction: dis.Instruction, position=-1):
        assert isinstance(instruction, dis.Instruction)

        if position == -1:
            self.instructions.append(instruction)
        else:
            self.instructions.insert(position, instruction)

    def add_all(self, instructions: typing.List[dis.Instruction], position=-1):
        if position == -1:
            self.instructions += instructions
        else:
            self.instructions = self.instructions[:position] + instructions + self.instructions[position:]

    def finalize(self):
        if self.instructions[-1].opcode != Opcodes.RETURN_VALUE:
            self.add_return(position=-1)

    def add_return(self, position=-1, constant=None, local_source=None):
        if local_source is not None:
            self.add(self.patcher.createLoadFast(local_source), position)
        else:
            self.add(self.patcher.createLoadConst(constant), position)
        self.add(createInstruction("RETURN_VALUE"), position)

