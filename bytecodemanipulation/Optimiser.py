import dis
import inspect
import math
import os
import re
import string
import struct
import types
import typing
import builtins
import random

from bytecodemanipulation.MutableFunctionHelpers import Guarantees
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.optimiser_util import inline_const_value_pop_pairs
from bytecodemanipulation.optimiser_util import inline_constant_binary_ops
from bytecodemanipulation.optimiser_util import inline_constant_method_invokes
from bytecodemanipulation.optimiser_util import inline_static_attribute_access
from bytecodemanipulation.optimiser_util import remove_branch_on_constant
from bytecodemanipulation.optimiser_util import remove_local_var_assign_without_use
from bytecodemanipulation.optimiser_util import remove_nops
from bytecodemanipulation.Specialization import SpecializationContainer
from bytecodemanipulation.util import _is_parent_of

BUILTIN_CACHE = builtins.__dict__.copy()

DISABLE_OPTIMISATION_APPLY = os.environ.setdefault("DISABLE_OPTIMISATION_APPLY", "")


class ValueIsNotArrivalException(Exception):
    pass


class BreaksOwnGuaranteesException(Exception):
    pass


class GlobalIsNeverAccessedException(Exception):
    pass


class _OptimisationContainer:
    _CUSTOM_TARGETS: typing.Dict[typing.Hashable, "_OptimisationContainer"] = {}
    _CONTAINERS: typing.List["_OptimisationContainer"] = []

    @classmethod
    def apply_all(cls):
        for target in cls._CONTAINERS:
            target.run_optimisers(False)

    @classmethod
    def get_for_target(
        cls,
        target: types.FunctionType | types.MethodType | typing.Type | types.ModuleType,
    ):

        if hasattr(target, "_OPTIMISER_CONTAINER"):
            return target._OPTIMISER_CONTAINER

        if target in cls._CUSTOM_TARGETS:
            return cls._CUSTOM_TARGETS[target]

        container = cls(target)

        cls._CONTAINERS.append(container)

        try:
            target._OPTIMISER_CONTAINER = container
        except (AttributeError, TypeError):
            cls._CUSTOM_TARGETS[target] = container

        return container

    def __init__(
        self,
        target: types.FunctionType | types.MethodType | typing.Type | types.ModuleType,
    ):
        self.target = target
        self.parents: typing.List["_OptimisationContainer"] = []
        self.children: typing.List["_OptimisationContainer"] = []
        self.optimisations: typing.List[AbstractOptimisationWalker] = []

        # Global names that are constant (e.g. imports)
        self.lazy_global_name_cache: typing.Dict[str, typing.Callable[[], object]] = {}
        self.dereference_global_name_cache: typing.Dict[str, object] = {
            "typing": typing,
        }
        self.unsafe_global_writes_allowed: typing.Set[str] = set()

        # Strict types for locals
        self.lazy_local_var_type: typing.Dict[
            str, typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_local_var_type: typing.Dict[str, typing.Type | None] = {}

        # Strict local attribute type
        self.lazy_local_var_attr_type: typing.Dict[
            typing.Tuple[str, str], typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_local_var_attr_type: typing.Dict[
            typing.Tuple[str, str], typing.Type
        ] = {}

        # Strict return type
        self.lazy_return_type: typing.Callable[[], typing.Type] | None = None
        self.dereference_return_type: typing.Type | None = None

        # Strict return attribute type
        self.lazy_return_attr_type: typing.Dict[
            str, typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_return_attr_type: typing.Dict[str, typing.Type] = {}

        # for classes: attribute strict type
        self.lazy_attribute_type: typing.Dict[
            str, typing.Callable[[], typing.Type]
        ] = {}
        self.dereference_attribute_type: typing.Dict[str, typing.Type] = {}

        # result is static based on parameters
        self.is_constant_op = False

        # invoking will not change the state of parameters or any other variable outside the scope
        self.is_side_effect_free_op = False

        # alternate function which can be invoked instead when the result is not needed, allows further optimisation
        self.side_effect_alternative: typing.Callable = None

        # attributes are never mutated
        self.is_static = False

        self.static_attributes: typing.Set[str] = set()

        self.try_inline_calls = False

        # Exceptions that can be raised from here
        self.may_raise_exceptions: typing.Set[
            typing.Type[Exception] | Exception
        ] | None = None

        self.specializations: typing.List[
            typing.Callable[[SpecializationContainer], None]
        ] = []

        self.is_optimized = False

        # Add the children to self
        if isinstance(self.target, type):
            for key, e in self.target.__dict__.items():
                if isinstance(
                    e,
                    (
                        type(guarantee_builtin_names_are_protected),
                        staticmethod,
                        classmethod,
                        type,
                    ),
                ):
                    if isinstance(e, (staticmethod, classmethod)):
                        func = e.__func__
                    else:
                        func = e

                    if (
                        func.__qualname__.startswith(self.target.__qualname__ + ".")
                        and func.__module__ == self.target.__module__
                    ):
                        self.children.append(self.get_for_target(e))

        self.guarantees: typing.List[Guarantees.AbstractGuarantee] | None = None

    def add_guarantee(self, guarantee: Guarantees.AbstractGuarantee):
        if self.guarantees is None:
            self.guarantees = []

        self.guarantees.append(guarantee)
        return self

    def is_attribute_static(self, name: str):
        return self.is_static or name in self.static_attributes

    def _walk_children_and_copy_attributes(self):
        for value in self.target.__dict__.values():
            if (
                isinstance(value, type)
                or inspect.ismethod(value)
                or inspect.isfunction(value)
                or isinstance(value, staticmethod)
            ):
                if _is_parent_of(value, self.target):
                    container = self.get_for_target(value)
                    container._copy_from(self)
                    self.children.append(container)

    def _copy_from(self, parent: "_OptimisationContainer"):
        self.parents.append(parent)

        self.lazy_global_name_cache.update(
            {
                key: value
                for key, value in parent.lazy_global_name_cache.items()
                if key not in self.lazy_global_name_cache
            }
        )
        self.dereference_global_name_cache.update(
            {
                key: value
                for key, value in parent.dereference_global_name_cache.items()
                if key not in self.dereference_global_name_cache
            }
        )
        self.unsafe_global_writes_allowed |= parent.unsafe_global_writes_allowed

        for child in self.children:
            child._copy_from(parent)

    def add_optimisation(self, optimiser: "AbstractOptimisationWalker"):
        self.optimisations.append(optimiser)
        return self

    def run_optimisers(self, warn=True):
        if self.is_optimized:
            if warn and not DISABLE_OPTIMISATION_APPLY:
                print("opt skipped", self.target)

            return

        self.is_optimized = True

        if DISABLE_OPTIMISATION_APPLY:
            return

        # print("opt", self.target)
        from bytecodemanipulation.optimiser_util import apply_specializations
        from bytecodemanipulation.MutableFunctionHelpers import (
            inline_calls_to_const_functions,
        )

        if self.children:
            self._walk_children_and_copy_attributes()

            for child in self.children:
                child.run_optimisers()

        # resolve the lazy types
        self._resolve_lazy_references()

        if not hasattr(self.target, "__code__") and not isinstance(
            self.target, (classmethod, staticmethod)
        ):
            return

        # Create mutable wrapper around the target
        mutable = MutableFunction.create(self.target)
        mutable.prepare_previous_instructions()

        # Walk over the code and resolve cached globals
        self._inline_load_globals(mutable)

        # Walk over the entries as long as the optimisers are doing their stuff
        while True:
            mutable.assemble_instructions_from_tree(
                mutable.instructions[0].optimise_tree()
            )
            mutable.prepare_previous_instructions()

            dirty = False
            for optimiser in self.optimisations:
                dirty = optimiser.apply(self, mutable) or dirty

            if dirty:
                continue

            if inline_const_value_pop_pairs(mutable):
                continue

            if remove_local_var_assign_without_use(mutable):
                continue

            # Inlines access to static items
            if inline_static_attribute_access(mutable):
                continue

            # Inline invokes to builtins and other known is_constant_op-s with static args
            if inline_constant_method_invokes(mutable):
                continue

            # Resolve known constant types
            if self._resolve_constant_local_types(mutable):
                continue
            # self._resolve_constant_local_attr_types(mutable)
            # todo: use return type of known functions

            if inline_constant_binary_ops(mutable):
                continue

            # apply optimisation specialisations
            if apply_specializations(mutable):
                continue

            # Inline invokes to builtins and other known is_constant_op-s with static args
            if inline_constant_method_invokes(mutable):
                continue

            # Remove conditional jumps no longer required
            if remove_branch_on_constant(mutable):
                continue

            if inline_calls_to_const_functions(mutable):
                continue

            break

        mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())

        mutable.reassign_to_function()

        # print(mutable)

    def _resolve_lazy_references(self):
        try:
            for key, lazy in self.lazy_global_name_cache.items():
                if key not in self.dereference_global_name_cache:
                    self.dereference_global_name_cache[key] = lazy()

            for key, lazy in self.lazy_local_var_type.items():
                if key not in self.dereference_local_var_type:
                    self.dereference_local_var_type[key] = lazy()

            for key, lazy in self.lazy_local_var_attr_type.items():
                if key not in self.dereference_local_var_attr_type:
                    self.dereference_local_var_attr_type[key] = lazy()

            if (
                self.dereference_return_type is None
                and self.lazy_return_type is not None
            ):
                self.dereference_return_type = self.lazy_return_type()

            for key, lazy in self.lazy_return_attr_type.items():
                if key not in self.dereference_return_attr_type:
                    self.dereference_return_attr_type[key] = lazy()

            for key, lazy in self.lazy_attribute_type.items():
                if key not in self.dereference_attribute_type:
                    self.dereference_attribute_type[key] = lazy()
        except:
            print(self.target)
            raise

    def _inline_load_globals(self, mutable: MutableFunction) -> bool:
        dirty = False

        for instruction in mutable.instructions:
            if instruction.opcode == Opcodes.LOAD_GLOBAL:
                if instruction.arg_value in self.dereference_global_name_cache:
                    name = instruction.arg_value
                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(
                        self.dereference_global_name_cache[name]
                    )
                    dirty = True

            elif instruction.opcode in (Opcodes.STORE_GLOBAL, Opcodes.DELETE_GLOBAL):
                if (
                    instruction.arg_value in self.dereference_global_name_cache
                    and instruction.arg_value not in self.unsafe_global_writes_allowed
                ):
                    raise BreaksOwnGuaranteesException(
                        f"Global {instruction.arg_value} is cached but written to!"
                    )

        return dirty

    def _resolve_constant_local_types(self, mutable: MutableFunction) -> bool:
        dirty = False

        for instruction in mutable.instructions:
            if instruction.opcode == Opcodes.LOAD_ATTR:
                try:
                    source = next(instruction.trace_stack_position(0))
                except StopIteration:
                    continue

                if source.opcode in (Opcodes.LOAD_FAST, Opcodes.LOAD_METHOD):
                    if source.arg_value not in self.dereference_local_var_type:
                        continue

                    data_type = self.dereference_local_var_type[source.arg_value]

                    if not hasattr(data_type, instruction.arg_value):
                        continue

                    # todo: check for dynamic class variables!

                    attr = getattr(data_type, instruction.arg_value)

                    instruction.change_opcode(Opcodes.LOAD_CONST)
                    instruction.change_arg_value(attr)
                    source.change_opcode(Opcodes.NOP)
                    dirty = True

        return dirty


_OptimisationContainer.get_for_target(typing).is_static = True
_OptimisationContainer.get_for_target(random).is_static = True
_OptimisationContainer.get_for_target(string).is_static = True
_OptimisationContainer.get_for_target(re).is_static = True
_OptimisationContainer.get_for_target(struct).is_static = True
_OptimisationContainer.get_for_target(math).is_static = True
_OptimisationContainer.get_for_target(os).is_static = True


class AbstractOptimisationWalker:
    """
    Optimisation walker for classes and functions, constructed by the optimiser annotations
    """

    def apply(
        self, container: "_OptimisationContainer", mutable: MutableFunction
    ) -> bool:
        """
        Applies this optimisation on the given container with the MutableFunction as target
        """
        raise NotImplementedError


def cache_global_name(
    name: str,
    accessor: typing.Callable[[], object] = None,
    ignore_unsafe_writes=False,
):
    """
    Allows the optimiser to cache a given global name ahead of execution.
    This can be used for e.g. constants, globals referencing a constant object, ...

    :param name: the global name, as accessed internally by the LOAD_GLOBAL instruction
    :param accessor: if needed (lazy init), a callable returning the value.
    May raise ValueIsNotArrivalException() when the result cannot currently be accessed.
    When this is raised, the optimiser might skip optimisation of this value.
    :param ignore_unsafe_writes: if the optimiser should ignore STORE_GLOBAL instructions writing to the same name as here cached
    :returns: an annotation for a function or class
    :raises BreaksOwnGuaranteesException: Raised at optimisation time when ignore_unsafe_writes is False and the global name accessed
    is written to in the same method.
    :raises GlobalIsNeverAccessedException: Raised at optimisation time when ignore_global_is_never_used is False and the global name is never
    accessed.
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        nonlocal accessor

        if accessor is None:
            accessor = lambda: target.__globals__.get(name)

        container.lazy_global_name_cache[name] = accessor

        if ignore_unsafe_writes:
            container.unsafe_global_writes_allowed.add(name)

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

        if white_list:
            container.dereference_global_name_cache.update(
                {
                    key: value
                    for key, value in BUILTIN_CACHE.items()
                    if key in white_list
                }
            )
        elif black_list:
            container.dereference_global_name_cache.update(
                {
                    key: value
                    for key, value in BUILTIN_CACHE.items()
                    if key not in black_list
                }
            )
        else:
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
        container.add_guarantee(Guarantees.ReturnType(data_type or lazy_data_type))

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

        exceptions_deref = set()

        for exception in exceptions:
            if isinstance(exception, Exception) or (
                isinstance(exception, typing.Type) and issubclass(exception, Exception)
            ):
                exceptions_deref.add(exception)
            elif callable(exception):
                exceptions_deref.add(exception())
            elif isinstance(exception, list):
                exceptions_deref |= {
                    exc
                    if isinstance(exc, Exception)
                    or (isinstance(exc, typing.Type) and issubclass(exc, Exception))
                    else exc()
                    for exc in exception
                }
            else:
                raise ValueError(exception)

        container.may_raise_exceptions = exceptions_deref

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

        if callable(module):
            container.lazy_global_name_cache[name] = module
        else:
            container.dereference_global_name_cache[name] = module

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
        container.add_guarantee(Guarantees.RESULT_IS_CONSTANT)

        return target

    return annotate


def guarantee_side_effect_free_call():
    """
    Guarantees that this function will not modify the state of anything associated, so it
    can be safely removed from the call chain of another function
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)
        container.is_side_effect_free_op = True

        return target

    return annotate


def guarantee_static_attributes(*attributes: str):
    """
    Marks attributes as static. If attributes (*...) is not empty, only the specified attributes are static,
    otherwise, all attributes are static.

    If guarantee_static_attributes is used without args, further calls with args will have no affect
    """

    def annotate(target):
        container = _OptimisationContainer.get_for_target(target)

        if not attributes:
            container.is_static = True
        else:
            container.static_attributes |= set(attributes)

        return target

    return annotate


def inline_calls(target: typing.Callable = None):
    def annot(tar):
        container = _OptimisationContainer.get_for_target(target)
        container.try_inline_calls = True
        return tar

    if target:
        return annot(target)
    return annot


def apply_now(target: typing.Callable = None):
    """
    Applies the optimisations NOW
    """

    def annotate(tar):
        # dis.dis(target)

        container = _OptimisationContainer.get_for_target(tar)
        container.run_optimisers()

        return tar

    if target:
        return annotate(target)
    return annotate


class IOptimised:
    """
    Implement this to apply optimisation on parts of the class

    Methods below the __init__subclass__ method can be called on the finished class for applying optimisation
    on some shared stuff.

    Annotate with above functions to apply method on whole classes / functions
    """

    _OPTIMISER_CONTAINER: _OptimisationContainer = None

    @classmethod
    def for_unbound_method(cls, target: typing.Callable) -> "IOptimised":
        raise NotImplementedError

    @classmethod
    def __init_subclass__(cls, **kwargs):
        cls._OPTIMISER_CONTAINER = _OptimisationContainer(cls)

    @classmethod
    def guarantee_this_attribute_exact_type(
        cls, attr_name: str, data_type: typing.Type | typing.Callable[[], typing.Type]
    ):
        if not isinstance(data_type, type):
            cls._OPTIMISER_CONTAINER.lazy_attribute_type[attr_name] = data_type
        else:
            cls._OPTIMISER_CONTAINER.dereference_attribute_type[attr_name] = data_type

        return cls
