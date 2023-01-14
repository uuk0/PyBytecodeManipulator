import typing

from bytecodemanipulation.MutableFunction import MutableFunction, Instruction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.assembler.Parser import Parser as AssemblyParser, JumpToLabel
from bytecodemanipulation.assembler import target as assembly_targets
from bytecodemanipulation.util import LambdaInstructionWalker


def apply_inline_assemblies(target: MutableFunction):
    """
    Processes all assembly() calls and label() calls in 'target'
    """

    labels = set()
    insertion_points: typing.List[typing.Tuple[str, Instruction]] = []

    for instr in target.instructions[:]:
        if instr.opcode == Opcodes.LOAD_GLOBAL:
            try:
                value = target.target.__globals__.get(instr.arg_value)
            except KeyError:
                continue

            if value == assembly_targets.assembly:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))
                assert arg.opcode == Opcodes.LOAD_CONST, "only constant assembly code is allowed!"

                insertion_points.append((arg.arg_value, invoke))

                instr.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)
                invoke.change_opcode(Opcodes.LOAD_CONST, None)

            elif value == assembly_targets.label:
                invoke = next(instr.trace_stack_position_use(0))
                arg = next(invoke.trace_stack_position(0))
                assert arg.opcode == Opcodes.LOAD_CONST, "only constant label names are allowed!"

                labels.add(arg.arg_value)
                invoke.change_opcode(Opcodes.BYTECODE_LABEL, arg.arg_value)
                invoke.insert_after(Instruction(target, -1, Opcodes.LOAD_CONST, None))
                instr.change_opcode(Opcodes.NOP)
                arg.change_opcode(Opcodes.NOP)

    assemblies = [
        AssemblyParser(code).parse()
        for code, _ in insertion_points
    ]

    for asm in assemblies:
        labels.update(asm.collect_label_info())

    for (_, instr), asm in zip(insertion_points, assemblies):
        bytecode = asm.create_bytecode(target, labels)
        if bytecode:
            instr.insert_after(bytecode)

    label_targets: typing.Dict[str, Instruction] = {}

    target.instructions[0].apply_visitor(LambdaInstructionWalker(lambda ins: (label_targets.__setitem__(ins.arg_value, ins), ins.change_opcode(Opcodes.NOP)) if ins.opcode == Opcodes.BYTECODE_LABEL else None))

    def visit(ins: Instruction):
        if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
            ins.change_arg_value(label_targets[instr.arg_value.name])

    target.instructions[0].apply_visitor(LambdaInstructionWalker(visit))

    return target.assemble_instructions_from_tree(target.instructions[0])

