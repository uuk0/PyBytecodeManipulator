import dis
import types
import typing

from bytecodemanipulation import Opcodes
from bytecodemanipulation.MutableCodeObject import createInstruction
from bytecodemanipulation.MutableCodeObject import MutableCodeObject


class BoundInstruction:
    def __init__(self, underlying: dis.Instruction, identifier: int):
        self.underlying = underlying
        self.identifier = identifier


class BytecodeBuilder:
    @classmethod
    def from_method_instance(cls, method: types.FunctionType):
        return cls.from_mutable_code_object(MutableCodeObject.from_function(method))

    @classmethod
    def from_mutable_code_object(cls, obj: MutableCodeObject):
        return cls.from_instruction_list(obj.get_instruction_list(), obj)

    @classmethod
    def from_instruction_list(cls, instructions: typing.List[dis.Instruction], mutable: MutableCodeObject):
        return cls(list(filter(lambda e: e.opcode != Opcodes.EXTENDED_ARG, instructions)), mutable)

    @classmethod
    def empty(cls):
        mutable = MutableCodeObject()
        return cls([], mutable)

    def __init__(self, instructions: typing.List[dis.Instruction], mutable: MutableCodeObject):
        self.instructions = instructions
        self.patcher = mutable

    def create_static_bound(self, position: int) -> BoundInstruction:
        pass

    def create_offset_bound(self, this: BoundInstruction, offset: int) -> BoundInstruction:
        pass

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

