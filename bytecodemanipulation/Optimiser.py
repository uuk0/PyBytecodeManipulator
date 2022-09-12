import typing
import builtins

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.optimiser_util import inline_constant_method_invokes
from bytecodemanipulation.optimiser_util import remove_branch_on_constant
from bytecodemanipulation.optimiser_util import remove_nops

BUILTIN_CACHE = builtins.__dict__.copy()


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

        self.lazy_global_name_cache: typing.Dict[str, typing.Callable[[], object]] = {}
        self.dereference_global_name_cache: typing.Dict[str, object] = {}

        self.lazy_local_var_type: typing.Dict[
            str, typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_local_var_type: typing.Dict[str, typing.Type | None] = {}

        self.lazy_local_var_attr_type: typing.Dict[
            typing.Tuple[str, str], typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_local_var_attr_type: typing.Dict[
            typing.Tuple[str, str], typing.Type
        ] = {}

        self.lazy_return_type: typing.Callable[[], typing.Type] | None = None
        self.dereference_return_type: typing.Type | None = None

        self.lazy_return_attr_type: typing.Dict[
            str, typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_return_attr_type: typing.Dict[str, typing.Type] = {}

        self.is_constant_op = False

    def add_optimisation(self, optimiser: "AbstractOptimisationWalker"):
        self.optimisations.append(optimiser)
        _ANNOTATIONS.append(optimiser)
        return self

    def run_optimisers(self):
        # resolve the lazy types
        self._resolve_lazy_references()

        # Create mutable wrapper around the target
        mutable = MutableFunction(self.target)

        dirty = True

        # Walk over the entries as long as the optimisers are doing their stuff
        while dirty:
            dirty = False

            # Walk over the code and resolve cached globals
            dirty = self._inline_load_globals(mutable) or dirty

            # Inline invokes to builtins and other known is_constant_op-s with static args
            dirty = inline_constant_method_invokes(mutable) or dirty

            # Resolve known constant types
            dirty = self._resolve_constant_local_types(mutable) or dirty
            # self._resolve_constant_local_attr_types(mutable)
            # todo: use return type of known functions

            # Inline invokes to builtins and other known is_constant_op-s with static args
            dirty = inline_constant_method_invokes(mutable) or dirty

            # Remove conditional jumps no longer required
            dirty = remove_branch_on_constant(mutable) or dirty

            remove_nops(mutable)

        mutable.assemble_instructions_from_tree(mutable.instructions[0])
        mutable.reassign_to_function()

    def _resolve_lazy_references(self):
        for key, lazy in self.lazy_global_name_cache.items():
            if key not in self.dereference_global_name_cache:
                self.dereference_global_name_cache[key] = lazy()
        for key, lazy in self.lazy_local_var_type.items():
            if key not in self.dereference_local_var_type:
                self.dereference_local_var_type[key] = lazy()
        for key, lazy in self.lazy_local_var_attr_type.items():
            if key not in self.dereference_local_var_attr_type:
                self.dereference_local_var_attr_type[key] = lazy()
        if self.dereference_return_type is None and self.lazy_return_type is not None:
            self.dereference_return_type = self.lazy_return_type()
        for key, lazy in self.lazy_return_attr_type.items():
            if key not in self.dereference_return_attr_type:
                self.dereference_return_attr_type[key] = lazy()

    def _inline_load_globals(self, mutable: MutableFunction) -> bool:
        dirty = False

        for instruction in mutable.instructions:
            if instruction.opcode == Opcodes.LOAD_GLOBAL:
                if instruction.arg_value in self.dereference_global_name_cache:
                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(
                        self.dereference_global_name_cache[instruction.arg_value]
                    )
                    dirty = True

            elif instruction.opcode in (Opcodes.STORE_GLOBAL, Opcodes.DELETE_GLOBAL):
                if instruction.arg_value in self.dereference_global_name_cache:
                    raise BreaksOwnGuaranteesException(
                        f"Global {instruction.arg_value} is cached but written to!"
                    )

        # todo: throw GlobalIsNeverAccessedException if wanted
        return dirty

    def _resolve_constant_local_types(self, mutable: MutableFunction) -> bool:
        dirty = False

        for instruction in mutable.instructions:
            if instruction.opcode == Opcodes.LOAD_ATTR:
                source = mutable.trace_stack_position(instruction.offset, 0)

                if source.opcode in (Opcodes.LOAD_FAST, Opcodes.LOAD_METHOD):
                    if source.arg_value not in self.dereference_local_var_type:
                        continue

                    data_type = self.dereference_local_var_type[source.arg_value]

                    if not hasattr(data_type, instruction.arg_value):
                        return

                    # todo: check for dynamic class variables!

                    attr = getattr(data_type, instruction.arg_value)

                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(attr)
                    source.change_opcode(Opcodes.NOP)
                    dirty = True

        return dirty


class AbstractOptimisationWalker:
    """
    Optimisation walker for classes and functions, constructed by the optimiser annotations
    """


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
        container.lazy_global_name_cache[name] = accessor

        return target

    return annotate


def guarantee_builtin_names_are_protected(
    white_list: typing.Iterable[str] = None, black_list: typing.Iterable[str] = None
):
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
        container.dereference_global_name_cache.update(BUILTIN_CACHE)

        return target

    return annotate


def guarantee_exact_local_type(
    local_name: str,
    data_type: typing.Type = None,
    lazy_data_type: typing.Callable[[], typing.Type] = None,
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
        container.lazy_local_var_type[local_name] = (
            lazy_data_type if lazy_data_type is not None else lambda: data_type
        )

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
        container.lazy_local_var_attr_type[(local_name, attr_name)] = (
            lazy_data_type if lazy_data_type is not None else lambda: data_type
        )

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
        container.lazy_return_type = (
            lazy_data_type if lazy_data_type is not None else lambda: data_type
        )

        return target

    return annotate


def guarantee_exact_return_attribute_type(
    attr_name: str,
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
        container.lazy_return_attr_type[attr_name] = (
            lazy_data_type if lazy_data_type is not None else lambda: data_type
        )

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
        container.is_constant_op = True

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