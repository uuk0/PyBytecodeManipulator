import typing


class ValueIsNotArrivalException(Exception):
    pass


class BreaksOwnGuaranteesException(Exception):
    pass


class GlobalIsNeverAccessedException(Exception):
    pass


class _OptimisationContainer:
    @classmethod
    def get_for_target(cls, target):
        if hasattr(target, "_OPTIMISER_CONTAINER"):
            return target._OPTIMISER_CONTAINER

        container = cls(target)
        target._OPTIMISER_CONTAINER = container
        return container

    def __init__(self, target):
        self.target = target
        self.parents: typing.List["_OptimisationContainer"] = []
        self.optimisations: typing.List[AbstractOptimisationWalker] = []

    def add_optimisation(self, optimiser: "AbstractOptimisationWalker"):
        self.optimisations.append(optimiser)
        _ANNOTATIONS.append(optimiser)
        return self


class AbstractOptimisationWalker:
    """
    Optimisation walker for classes and functions, constructed by the optimiser annotations
    """


class _CacheGlobalOptimisationWalker(AbstractOptimisationWalker):
    def __init__(
        self,
        name: str,
        accessor: typing.Callable[[], object] = None,
        ignore_unsafe_writes=False,
        ignore_global_is_never_used=False,
    ):
        self.name = name
        self.accessor = accessor
        self.ignore_unsafe_writes = ignore_unsafe_writes
        self.ignore_global_is_never_used = ignore_global_is_never_used


def cache_global_name(
    name: str,
    accessor: typing.Callable[[], object] = None,
    ignore_unsafe_writes=False,
    ignore_global_is_never_used=False,
):
    """
    Allows the optimiser to cache a given global name ahead of execution.
    This can be used for e.g. constants, globals referencing a constant object, ...

    :param name: the global name, as accessed internally by the LOAD_GLOBAL instruction
    :param accessor: if needed (lazy init), a callable returning the value.
    May raise ValueIsNotArrivalException() when the result cannot currently be accessed.
    When this is raised, the optimiser might skip optimisation of this value.
    :param ignore_unsafe_writes: if the optimiser should ignore STORE_GLOBAL instructions writing to the same name as here cached
    :param ignore_global_is_never_used: if the optimiser should ignore if no LOAD_GLOBAL instruction accesses this global
    :returns: an annotation for a function or class
    :raises BreaksOwnGuaranteesException: Raised at optimisation time when ignore_unsafe_writes is False and the global name accessed
    is written to in the same method.
    :raises GlobalIsNeverAccessedException: Raised at optimisation time when ignore_global_is_never_used is False and the global name is never
    accessed.
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)
        container.add_optimisation(
            _CacheGlobalOptimisationWalker(
                name,
                accessor,
                ignore_unsafe_writes,
                ignore_global_is_never_used,
            )
        )

        return target

    return annotate


def guarantee_builtin_names_are_protected():
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_local_type(
    local_name: str, data_type: typing.Type | typing.Callable[[], typing.Type]
):
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_local_var_attribute_type(
    local_name: str,
    attr_name: str,
    data_type: typing.Type | typing.Callable[[], typing.Type],
):
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_return_type(
    data_type: typing.Type | typing.Callable[[], typing.Type]
):
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_return_attribute_type(
    name: str, data_type: typing.Type | typing.Callable[[], typing.Type]
):
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_may_raise_only(
    *exceptions: Exception
    | typing.List[Exception | typing.Callable[[], Exception]]
    | typing.Callable[[], Exception]
):
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_module_import(
    name: str, module: type(typing) | typing.Callable[[], type(typing)]
):
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_constant_result():
    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


_ANNOTATIONS = []


class IOptimised:
    """
    Implement this to apply optimisation on parts of the class

    Methods below the __init__subclass__ method can be called on the finished class for applying optimisation
    on some shared stuff.

    Annotate with above functions to apply method on whole classes / functions
    """

    _OPTIMISER_ANNOTATIONS = []

    @classmethod
    def for_unbound_method(cls, target: typing.Callable) -> "IOptimised":
        raise NotImplementedError

    @classmethod
    def __init_subclass__(cls, **kwargs):
        cls._OPTIMISER_ANNOTATIONS = cls._OPTIMISER_ANNOTATIONS + _ANNOTATIONS
        _ANNOTATIONS.clear()

    @classmethod
    def ignore_optimiser_exceptions(cls):
        return cls

    @classmethod
    def guarantee_this_attribute_exact_type(
        cls, attr_name: str, data_type: typing.Type | typing.Callable[[], typing.Type]
    ):
        return cls
