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


def guarantee_builtin_names_are_protected(white_list: typing.Iterable[str] = None, black_list: typing.Iterable[str] = None):
    """
    Annotation marking all builtin names as protected, meaning they can be cached

    :param white_list: if provided, only builtins named as entries in the iterable will be optimised
    :param black_list: if provided, only builtins NOT in this list will be optimised
    :raises ValueError: when both white_list and black_list are provided
    :raises BreaksOwnGuaranteesException: (at optimisation time) if a write to an optimise-able builtin name is detected
    """

    if white_list is not None and black_list is not None:
        raise ValueError("Both white list and black list are provided!")

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_local_type(
    local_name: str, data_type: typing.Type = None, lazy_data_type: typing.Callable[[], typing.Type] = None
):
    """
    Guarantees that the given local name has the exact type. Not a subclass of it.

    The optimiser is allowed to use this type of optimisation when it detects a static data type
    (e.g. a single write with a predictable exact type, e.g. constants)

    :param local_name: the local name provided
    :param data_type: the data type the local has
    :param lazy_data_type: or a getter for the data type
    :raises ValueError: if both data_type and lazy_data_type are provided
    """

    if data_type is not None and lazy_data_type is not None:
        raise ValueError("Both data_type and lazy_data_type are provided!")

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_local_var_attribute_type(
    local_name: str,
    attr_name: str,
    data_type: typing.Type = None,
    lazy_data_type: typing.Callable[[], typing.Type] = None,
):
    """
    Similar to guarantee_exact_local_type(), but set the data type of an attribute of a local.
    This resembles the concept of dynamic attributes, with case-to-case known data values.

    :param local_name: the local name provided
    :param attr_name: the attribute name of the local
    :param data_type: the data type the local has
    :param lazy_data_type: or a getter for the data type
    :raises ValueError: if both data_type and lazy_data_type are provided
    """

    if data_type is not None and lazy_data_type is not None:
        raise ValueError("Both data_type and lazy_data_type are provided!")

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_return_type(
    data_type: typing.Type = None,
    lazy_data_type: typing.Callable[[], typing.Type] = None,
):
    """
    The other side of guarantee_exact_local_type(), inferred by the function called,
    so the other side can optimise for this data type.
    Requires the exact function to be known at optimisation time.
    :param data_type: the data type the local has
    :param lazy_data_type: or a getter for the data type
    :raises ValueError: if both data_type and lazy_data_type are provided
    """

    if data_type is not None and lazy_data_type is not None:
        raise ValueError("Both data_type and lazy_data_type are provided!")

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_exact_return_attribute_type(
    data_type: typing.Type = None,
    lazy_data_type: typing.Callable[[], typing.Type] = None,
):
    """
    The guarantee_exact_local_var_attribute_type() variant of guarantee_exact_return_type()
    """

    if data_type is not None and lazy_data_type is not None:
        raise ValueError("Both data_type and lazy_data_type are provided!")

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_may_raise_only(
    *exceptions: Exception
    | typing.List[Exception | typing.Callable[[], Exception]]
    | typing.Callable[[], Exception]
    | Exception
):
    """
    Guarantees that this function may only raise the given exceptions, provided in direct or lazy form, and
    optional in single-instance
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_module_import(
    name: str, module: type(typing) | typing.Callable[[], type(typing)]
):
    """
    Guarantees that a given GLOBAL name is imported, and provides the module or a lazy module getter for it
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_constant_result():
    """
    Guarantees that this function will return the same value if invoked with the same args
    Implies that the function does NOT modify the args again if seen again.
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def guarantee_constant_state_unless():
    """
    Guarantees that all methods on this object are non-state-changing, excluding functions annotated with changes_object_state()
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        return target

    return annotate


def changes_object_state():
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
