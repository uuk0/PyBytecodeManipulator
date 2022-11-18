import typing

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


class TypeAnnotation:
    pass


class MethodCallDescriptor:
    def __init__(self, lookup_method_instr: Instruction = None, call_method_instr: Instruction = None):
        self.lookup_method_instr: Instruction = lookup_method_instr
        self.call_method_instr: Instruction = call_method_instr


class ArgDescriptor:
    def __init__(self, real: Instruction, normal: Instruction, arg_id: int):
        self.real = real
        self.normal = normal
        self.arg_id = arg_id
        self.is_self = False
        self.discarded = False
        self.parent: "SpecializationContainer" = None

    def get_real_data_instr(self) -> Instruction:
        return self.real

    def get_normalized_data_instr(self) -> Instruction:
        return self.normal

    def get_type_annotation(self) -> TypeAnnotation:
        pass

    def discard(self):
        self.discarded = True

        if self.parent:
            self.parent.no_special = False


class SpecializationContainer:
    def __init__(self):
        self.underlying_function: MutableFunction | None = None
        self.method_call_descriptor: MethodCallDescriptor | None = None
        self.arg_descriptors: typing.List[ArgDescriptor] = []
        self.return_type_annotation: TypeAnnotation | None = None

        self.no_special = True
        self.result_arg: ArgDescriptor | None = None

    def set_arg_descriptors(self, descriptors: typing.List[ArgDescriptor]):
        for e in descriptors:
            e.parent = self

        self.arg_descriptors[:] = descriptors

    def get_arg_specification(self, arg: int) -> ArgDescriptor:
        return self.arg_descriptors[arg]

    def get_arg_specifications(self) -> typing.List[ArgDescriptor]:
        return self.arg_descriptors

    def get_return_type(self) -> TypeAnnotation:
        return self.return_type_annotation

    def replace_with_constant_value(self, value: object, side_effect: typing.Callable[[...], None] = None):
        pass

    def replace_with_variant(self, target: typing.Callable[[...], object]):
        pass

    def replace_with_raise_exception(self, exception: Exception, side_effect: typing.Callable[[...], None] = None):
        pass

    def replace_call_with_opcodes(self, opcodes: typing.List[Instruction]):
        """
        Replaces the call with a set of instructions.
        The instructions must be bound to the underlying function objects
        Arguments are at head like for the call instruction, skipping possible
        discard()-ed arguments.
        """

    def replace_call_with_arg(self, arg: ArgDescriptor):
        """
        Replaces the function call with a constant argument return
        Automatically discards all other arguments
        """

        if arg not in self.arg_descriptors:
            raise ValueError(arg)

        self.no_special = False
        self.result_arg = arg

    def apply(self):
        if self.no_special:
            return

        if self.result_arg:
            for arg in self.arg_descriptors:
                if arg != self.result_arg:
                    arg.discard()

            self._discard_args()
            self.method_call_descriptor.lookup_method_instr.change_opcode(Opcodes.NOP)
            self.method_call_descriptor.call_method_instr.change_opcode(Opcodes.NOP)

    def _discard_args(self):
        for arg in self.arg_descriptors:
            if arg.discarded:
                # todo: safe-guard
                arg.get_real_data_instr().change_opcode(Opcodes.NOP)


def register(target: typing.Callable):
    def annotation(special: typing.Callable[[SpecializationContainer], None]):
        from bytecodemanipulation.Optimiser import _OptimisationContainer

        _OptimisationContainer.get_for_target(target).specializations.append(special)

        return special

    return annotation

