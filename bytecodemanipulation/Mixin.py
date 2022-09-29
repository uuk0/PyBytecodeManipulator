import importlib
import typing
from abc import ABC

from bytecodemanipulation.MutableFunction import AbstractInstructionWalker
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.Opcodes import Opcodes


class MixinInjectionNotSupportedException(Exception): pass


class _MixinContainer:
    class MixinFunctionContainer:
        def __init__(self, target: typing.Callable):
            self.target = target
            self.mixins: typing.List[Mixin._MixinFunctionContainer] = []

        def sort_and_apply(self):
            pass

        def reset(self):
            pass

        def run_optimiser(self):
            pass

    @classmethod
    def get_container_for_target(cls, target: typing.Type) -> "_MixinContainer":
        if hasattr(target, "_MIXIN_CONTAINER"):
            return getattr(target, "_MIXIN_CONTAINER")

        container = _MixinContainer(target)
        target._MIXIN_CONTAINER = container
        return container

    def __init__(self, target: typing.Type):
        self.target = target
        self.mixins: typing.List["Mixin"] = []
        self.function_containers: typing.Dict[
            str, _MixinContainer.MixinFunctionContainer
        ] = {}

    def sort_and_apply(self):
        pass

    def reset(self):
        pass

    def run_optimiser(self):
        pass


class InjectionPosition:
    class AbstractInjectionPosition(AbstractInstructionWalker, ABC):
        def __init__(self):
            self._positions: typing.List[Instruction] = []

        def get_positions(self, root: Instruction) -> typing.List[Instruction]:
            self._positions.clear()
            self.init()
            root.apply_visitor(self)
            positions = self._positions.copy()
            self._positions.clear()
            return positions

        def mark(self, instruction: Instruction):
            self._positions.append(instruction)

        def init(self):
            pass

        def visit(self, instruction: Instruction):
            raise NotImplementedError

    class _AtHeadInject(AbstractInjectionPosition):
        def __init__(self):
            super().__init__()
            self.has_met_instr = False

        def init(self):
            self.has_met_instr = False

        def visit(self, instruction: Instruction):
            if not self.has_met_instr:
                self.mark(instruction)
                self.has_met_instr = True

    HEAD = _AtHeadInject()

    class _AtFirstReturn(AbstractInjectionPosition):
        def visit(self, instruction: Instruction):
            if instruction.opcode == Opcodes.RETURN_VALUE and not self._positions:
                self.mark(instruction)

    FIRST_RETURN = _AtFirstReturn()

    class _AtLastReturn(AbstractInjectionPosition):
        def visit(self, instruction: Instruction):
            if instruction.opcode == Opcodes.RETURN_VALUE:
                self._positions.clear()
                self.mark(instruction)

    LAST_RETURN = _AtLastReturn()

    class _AtReturn(AbstractInjectionPosition):
        def visit(self, instruction: Instruction):
            if instruction.opcode == Opcodes.RETURN_VALUE:
                self.mark(instruction)

    ALL_RETURN = _AtReturn()


def override(target_name: str, soft_override=False):
    """
    Overrides the target method

    :param target_name: the function name
    :param soft_override: if True, applies it only when no other mixin is applied, otherwise,
        this may result in a crash when multiple are mixing into
    """


def inject_at(target_name: str, position: InjectionPosition.AbstractInjectionPosition, deduplicate=False):
    """
    Injects the target at the specified position

    :param target_name: the function name
    :param position: the position to inject at, might be 0 - inf
    :param deduplicate: when True, tries to remove duplicated code segments by jumping around
    """


def exception_handle(target_name: str, exception_type: typing.Type[Exception], start: InjectionPosition.AbstractInjectionPosition = None, end: InjectionPosition.AbstractInjectionPosition = None):
    """
    Adds a new exception handle, overriding the existing exception handles for the type in the region.

    :param target_name: the function name
    :param exception_type: the type of the exception to handle
    :param start: where the exception handle starts, by default HEAD
    :param end: where the exception handle ends, by default end of function
    """


def inject_by_known_call(target_name: str, invoke_target: typing.Callable, checker: InjectionPosition.AbstractInjectionPosition, replace=False, before=False):
    """
    Injects the target at a function call, specified by exact function.

    Parameters to the call might be accessed via resolve_prepared_parameter(<i>) where i is a constant, including slice.

    Use override_function_call_result(<value>) to replace the result of the call when replace is False.

    :param target_name: the function name
    :param invoke_target: what function calls to inject at
    :param checker: check function for each position
    :param replace: if True, replaces the function call, otherwise, injects around
    :param before: only affective if replace is False. If True, the target will be injected before the targeted call,
        otherwise, behind, making the result arrival via resolve_prepared_parameter(-1)
    """


def inject_by_named_call(target_name: str, invoke_target: str, checker: InjectionPosition.AbstractInjectionPosition, replace=False, before=False):
    """
    Injects the target at a function call, specified by exact function.

    Parameters to the call might be accessed via resolve_prepared_parameter(<i>) where i is a constant, including slice.

    Use override_function_call_result(<value>) to replace the result of the call when replace is False.

    :param target_name: the function name
    :param invoke_target: what function name calls to inject at
    :param checker: check function for each position
    :param replace: if True, replaces the function call, otherwise, injects around
    :param before: only affective if replace is False. If True, the target will be injected before the targeted call,
        otherwise, behind, making the result arrival via resolve_prepared_parameter(-1)
    """


def inject_by_named_call_on_known_type(target_name: str, obj_type: type, invoke_target: str, checker: InjectionPosition.AbstractInjectionPosition, replace=False, before=False):
    """
    Injects the target at a function call, specified by exact function.

    Parameters to the call might be accessed via resolve_prepared_parameter(<i>) where i is a constant, including slice.

    Use override_function_call_result(<value>) to replace the result of the call when replace is False.

    :param target_name: the function name
    :param obj_type: what type the object needs, can be None for static methods loaded from e.g. global namespace
    :param invoke_target: what function name calls to inject at
    :param checker: check function for each position
    :param replace: if True, replaces the function call, otherwise, injects around
    :param before: only affective if replace is False. If True, the target will be injected before the targeted call,
        otherwise, behind, making the result arrival via resolve_prepared_parameter(-1)
    """


class Mixin:
    """
    Mixin class providing an abstract interface for bytecode manipulation

    Example use:

    class TestClass:
        def test():
            return 0

    @Mixin(TestClass)
    class TestClassMixin(Mixin.Interface):
        @override("test")
        def test():
            return 1

    The result of TestClass.test() will be without the mixin 0, with it 1
    """

    _INSTANCES: typing.List["Mixin"] = []

    @classmethod
    def _reset(cls):
        cls._INSTANCES.clear()

    @classmethod
    def for_unbound_method(cls, target: typing.Callable) -> "Mixin":
        raise NotImplementedError

    class Interface:
        """
        @Mixin-annotated classes MUST implement this so the neat helper functions can be used
        """

        MIXIN_CONTAINER: _MixinContainer = None

        @classmethod
        def resolve_local(cls, name: str) -> object:
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def resolve_exception_instance(cls) -> Exception:
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def resolve_prepared_parameter(cls, index: int) -> object:
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def resolve_cell_variable(cls, name: str) -> object:
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def return_outer(cls, value=None):
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def jump_to(cls, position: InjectionPosition.AbstractInjectionPosition):
            # todo: check that <position> only matches one position
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def jump_to_exception_handler(cls, exception_type: Exception | typing.Type[Exception]):
            raise MixinInjectionNotSupportedException("Not implemented!")

        @classmethod
        def override_function_call_result(cls, result: object):
            raise MixinInjectionNotSupportedException("Not implemented!")

    class _MixinFunctionContainer:
        pass

    def __init__(
        self,
        target_class: str | typing.Type | typing.Callable[[], typing.Type],
        priority=0,
        optional=False,
        apply_on_others=True,
    ):
        if not callable(target_class) and not isinstance(target_class, str):
            raise ValueError(
                f"'target_class' must be str (for resolving), class or lazy class, got {type(target_class)}"
            )

        self.__target_class = target_class
        self.__resolved = False
        self.__mixin_class: typing.Optional[typing.Type[Mixin.Interface]] = None
        self.__mixin_container: typing.Optional[_MixinContainer] = None
        self.__priority = priority
        self.__optional = optional
        self.__apply_on_others = apply_on_others

        Mixin._INSTANCES.append(self)

    def __call__(self, cls: typing.Type):
        if self.__mixin_class is not None:
            raise ValueError("Can only annotate one class with one Mixin-instance!")

        if not issubclass(cls, Mixin.Interface):
            raise ValueError(
                "@Mixin-annotated classes must implement the Mixin.Interface!"
            )

        self.__mixin_class = cls

    def _resolve(self) -> bool:
        self.__resolved = True

        if isinstance(self.__target_class, str):
            if ":" not in self.__target_class:
                self.__target_class = importlib.import_module(self.__target_class)
                return True

            module, path = self.__target_class.split(":")
            module = importlib.import_module(module)

            for e in path.split("."):
                module = getattr(module, e)

            self.__target_class = module
            return True

        try:
            issubclass(self.__target_class, Mixin.Interface)
        except TypeError:
            pass
        else:
            return True

        self.__target_class = self.__target_class()
        return True

    def _bind_to_target(self):
        if not self.__resolved:
            raise RuntimeError("_resolve() must be called before _bind_to_target()")

        self.__mixin_container = (
            container
        ) = (
            self.__mixin_class.MIXIN_CONTAINER
        ) = _MixinContainer.get_container_for_target(self.__target_class)
        container.mixins.append(self)
