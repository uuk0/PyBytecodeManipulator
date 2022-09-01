import importlib
import typing


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


class Mixin:
    """
    Mixin class providing an abstract interface for bytecode manipulation

    Example use:

    class TestClass:
        def test():
            pass

    @Mixin(TestClass)
    class TestClassMixin(Mixin.Interface):
        pass
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
