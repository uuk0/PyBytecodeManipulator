import typing

from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import AbstractInstructionWalkerTransform
from bytecodemanipulation.opcodes.Opcodes import Opcodes

if typing.TYPE_CHECKING:
    from bytecodemanipulation.opcodes.Instruction import Instruction
    from bytecodemanipulation.MutableFunction import MutableFunction
    from bytecodemanipulation.opcodes.CodeObjectBuilder import CodeObjectBuilder


class ExceptionInstructionDecoder(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", metadata: typing.List["Instruction"], target: "Instruction") -> typing.Any:
        if target.opcode == Opcodes.SETUP_FINALLY:
            handle = target.arg_value
            target.change_opcode(Opcodes.NOP)
            finalized_instructions = set()
            pending_instructions = set(target.get_following_instructions())

            while pending_instructions:
                instr = pending_instructions.pop()

                if instr not in finalized_instructions:
                    if instr.opcode != Opcodes.POP_BLOCK:
                        finalized_instructions.add(instr)
                        pending_instructions |= set(instr.get_following_instructions())
                    else:
                        instr.change_opcode(Opcodes.NOP)

            function.exception_table.add_handle(handle, finalized_instructions)


class ExceptionInstructionEncoder(AbstractInstructionWalkerTransform):
    @classmethod
    def visit(cls, function: "MutableFunction", builder: "CodeObjectBuilder", target: "Instruction"):
        # todo: how to handle overlapping but not fully overlapping spans?

        for handle, span in function.exception_table.table.items():
            handled = set()

            for item in span:
                following = set(item.get_following_instructions())

                if not following or not all(e in span for e in following):
                    from bytecodemanipulation.opcodes.Instruction import Instruction

                    block_exit = Instruction(Opcodes.POP_BLOCK)

                    item.insert_after(block_exit)
                    handled.add(block_exit)
                else:
                    handled |= following

                if item not in handled:
                    new_item = item.copy()
                    item.insert_after(new_item)
                    item.change_opcode(Opcodes.SETUP_FINALLY, handle)

                    handled |= {item, new_item}

        function.exception_table.table.clear()

