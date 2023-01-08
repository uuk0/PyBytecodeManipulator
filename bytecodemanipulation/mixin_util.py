import typing

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


def resolve_accesses(
    inject_target: MutableFunction, injected: MutableFunction
) -> typing.List[str]:
    BOUND_LOCALS = {}
    BOUND_CELL_VARIABLES = {}

    for instruction in injected.instructions:
        if instruction.has_local():
            instruction.change_arg_value(
                injected.function_name + "::" + instruction.arg_value
            )

    for instruction in injected.instructions:
        if (
            instruction.opcode in (Opcodes.CALL_METHOD, Opcodes.CALL_FUNCTION)
            and instruction.arg <= 1
        ):
            source = next(instruction.trace_stack_position(instruction.arg))

            if source.opcode == Opcodes.LOAD_CONST:
                target = source.arg_value

                if not isinstance(target, classmethod):
                    continue

                func_name = target.__name__
                is_const = True
                source_source = None
            elif source.opcode in (Opcodes.LOAD_ATTR, Opcodes.LOAD_METHOD):
                source_source = next(source.trace_stack_position(0))

                if (
                    source_source.opcode == Opcodes.LOAD_FAST
                    and source_source.arg_value in ("self", "cls")
                ):
                    func_name = source.arg_value
                    is_const = False
                else:
                    continue
            else:
                continue

            if func_name == "resolve_local":
                assert (
                    instruction.arg == 1
                ), f"resolve_local() must be invoked with exactly one arg, got {instruction.arg}"

                variable_name = next(instruction.trace_stack_position(0))

                assert (
                    variable_name.opcode == Opcodes.LOAD_CONST
                ), f"resolve_local(<xy>) MUST be invoked with a constant, got {instruction}"

                target = next(instruction.trace_stack_position_use(0))

                if target.opcode == Opcodes.STORE_FAST:
                    BOUND_LOCALS[target.arg_value] = variable_name.arg_value
                else:
                    instruction.change_opcode(Opcodes.LOAD_FAST)
                    instruction.change_arg_value(variable_name.arg_value)
                    source.change_opcode(Opcodes.NOP)

                    if not is_const:
                        source_source.change_opcode(Opcodes.NOP)

            elif func_name == "resolve_cell_variable":
                assert (
                    instruction.arg == 1
                ), f"resolve_cell_variable() must be invoked with exactly one arg, got {instruction.arg}"

                variable_name = next(instruction.trace_stack_position(0))

                assert (
                    variable_name.opcode == Opcodes.LOAD_CONST
                ), f"resolve_cell_variable(<xy>) MUST be invoked with a constant, got {instruction}"

                target = next(instruction.trace_stack_position_use(0))

                if target.opcode == Opcodes.STORE_FAST:
                    BOUND_CELL_VARIABLES[target.arg_value] = variable_name
                else:
                    instruction.change_opcode(Opcodes.LOAD_DEREF)
                    instruction.change_arg_value(variable_name.arg_value)

                    instruction.change_arg_value(variable_name.arg_value)
                    source.change_opcode(Opcodes.NOP)

                    if not is_const:
                        source_source.change_opcode(Opcodes.NOP)

        elif instruction.has_local():
            if instruction.arg_value in BOUND_LOCALS:
                instruction.change_arg_value(BOUND_LOCALS[instruction.arg_value])
            elif instruction.arg_value in BOUND_CELL_VARIABLES:
                instruction.change_opcode(instruction.opname.replace("FAST", "DEREF"))
                instruction.change_arg_value(
                    BOUND_CELL_VARIABLES[instruction.arg_value]
                )

    return list(BOUND_LOCALS.keys())
