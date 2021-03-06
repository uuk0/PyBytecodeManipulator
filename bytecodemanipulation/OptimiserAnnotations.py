import builtins
import importlib
import sys
import traceback
import types
import typing

from bytecodemanipulation.MutableCodeObject import createInstruction

from . import CodeOptimiser
from bytecodemanipulation.InstructionMatchers import AbstractInstructionMatcher
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.BytecodeProcessors import (
    AbstractBytecodeProcessor,
    MethodInlineProcessor,
    Global2ConstReplace,
    SideEffectFreeMethodCallRemover,
    EvalAtOptimisationTime,
    StandardLibraryResolver,
    StandardLibraryAllResolver,
    StaticObjectAccessorResolver,
)
from .BytecodeProcessors import GlobalStaticLookupProcessor
from .InstructionMatchers import MetaArgMatcher
from .util import Opcodes
from .CodeOptimiser import optimise_code

"""
The following annotations should be also added:
- variable type forces (-> look methods statically up)
- annotations for protected methods (-> no override)
- hinting that ...[...] looks up in a dict (-> static method resolving)
"""


def _is_builtin_name(_, name: str):
    return hasattr(builtins, name)


def next_cycle():
    """
    Cycles the internal system to the next cycle
    affects only the optimised methods with a cycle cache
    """


def invalidate_cache(function, obj=None):
    """
    Clears the internal function cache

    :param function: the function object
    :param obj: when the target is object bound, this is the object
    """


class _OptimiserContainer:
    CONTAINERS: typing.List["_OptimiserContainer"] = []

    def __init__(self, target: typing.Union[typing.Callable, typing.Type]):
        self.target = target
        self.is_constant = False
        self.is_self_constant = False
        self.constant_args: typing.Set[str] = set()
        self.code_walkers: typing.List[AbstractBytecodeProcessor] = []
        self.specified_locals: typing.Dict[str, typing.Type] = {}
        self.return_type: typing.Optional[typing.Type] = None
        self.is_side_effect_free = False

        self.attribute_type_marks: typing.Dict[str, typing.Type] = {}

        if hasattr(target, "__bases__"):
            parents = set(target.__bases__) - {object, type}
            while parents:
                parent = parents.pop()
                if hasattr(parent, "optimiser_container"):
                    container: _OptimiserContainer = parent.optimiser_container
                    self.attribute_type_marks.update(container.attribute_type_marks)
                parents |= set(parent.__bases__) - {object, type}

        # Optional: a list of attributes accessed by this method on the bound object
        self.touches: typing.Optional[typing.Set[str]] = None

        # self.evaluate_touches()

    def evaluate_touches(self):
        if isinstance(self.target, types.FunctionType):
            helper = BytecodePatchHelper(self.target)

            self.touches = set()

            for index, instr in helper.walk():
                if instr.opcode == Opcodes.STORE_ATTR:
                    source_instruction = next(helper.findSourceOfStackIndex(index, 0))

                    if (
                        source_instruction.opcode == Opcodes.LOAD_FAST
                        and source_instruction.argval == "self"
                    ):
                        self.touches.add(instr.argval)

                elif instr.opname == helper.CALL_FUNCTION_NAME:
                    method_source = next(
                        helper.findSourceOfStackIndex(index, -instr.arg)
                    )

                    try:
                        source = helper.evalStaticFrom(method_source)
                    except ValueError:
                        pass
                    else:
                        if hasattr(source, "optimiser_container"):
                            container = source.optimiser_container

                            if container.is_constant:
                                continue

                    self.touches = None
                    return

            if len(self.touches) == 0:
                self.is_self_constant = True

    def optimise_target(self):
        if "--disable-bytecode-optimisation" in sys.argv:
            return

        if isinstance(self.target, types.FunctionType):
            self.optimise_method(self.target)
        else:
            for value in self.target.__dict__.values():
                # Second condition checks if the function is a member of that class
                if isinstance(value, types.FunctionType) and value.__qualname__.split(".")[-2] == self.target.__name__:
                    self.optimise_attribute_access_for_self_method(value)
                    self.optimise_method(value)

    def optimise_method(self, target: types.FunctionType):
        helper = BytecodePatchHelper(target)

        for processor in self.code_walkers:
            print(f"[INFO] applying optimiser transformer {processor} onto {target}")
            processor.apply(None, helper.patcher, helper)
            helper.re_eval_instructions()

        optimise_code(helper)

        helper.store()
        helper.patcher.applyPatches()
        CodeOptimiser.optimise_code(helper)

    def optimise_attribute_access_for_self_method(self, target: types.FunctionType):
        # todo: move to optimise module
        # Only if that map is populated, we can work
        if not self.attribute_type_marks: return

        helper = BytecodePatchHelper(target)

        index = -1

        while index < len(helper.instruction_listing):
            index += 1

            for index, instr in list(helper.walk())[index:]:
                if instr.opcode == Opcodes.LOAD_METHOD:
                    previous = helper.instruction_listing[index - 1]

                    if previous.opcode == Opcodes.LOAD_ATTR:
                        source = next(helper.findSourceOfStackIndex(index - 1, 0))
                        # print(source)
                        # print(instr)
                        # print(previous)

                        if source.opcode == Opcodes.LOAD_FAST and source.argval == "self":
                            if previous.argval in self.attribute_type_marks:
                                value_type = self.attribute_type_marks[previous.argval]
                                static_method_descriptor = getattr(value_type, instr.argval)

                                try:
                                    invoke_target = next(helper.findTargetOfStackIndex(index, 0))
                                except NotImplementedError as e:
                                    traceback.print_exc()
                                    print(e.args)
                                    continue

                                helper.instruction_listing[invoke_target.offset // 2] = createInstruction(
                                    Opcodes.CALL_FUNCTION,
                                    invoke_target.arg + 1,
                                )
                                helper.instruction_listing[source.offset // 2] = helper.patcher.createLoadConst(static_method_descriptor)
                                helper.instruction_listing[index - 1] = source
                                helper.instruction_listing[index] = previous
                                helper.re_eval_instructions()

                                # LOAD_FAST <self>   index - 2
                                # LOAD_ATTR <attr>   index - 1
                                # LOAD_METHOD <name> index
                                # ...
                                # CALL_METHOD <args>
                                # ->
                                # LOAD_CONST <method> index - 2
                                # LOAD_FAST <self>    index - 1
                                # LOAD_ATTR <attr>    index
                                # ...
                                # CALL_METHOD <args + 1>
                                index -= 1
                                break
            else:
                break

        helper.store()
        helper.patcher.applyPatches()

    async def optimize_target_async(self):
        try:
            self.optimise_target()
        except:
            print(self.target)
            raise


def _schedule_optimisation(
    target: typing.Union[typing.Callable, typing.Type],
) -> _OptimiserContainer:
    if "optimiser_container" not in target.__dict__:
        target.optimiser_container = _OptimiserContainer(target)
        _OptimiserContainer.CONTAINERS.append(target.optimiser_container)

    return target.optimiser_container


def run_optimisations():
    for instance in _OptimiserContainer.CONTAINERS:
        instance.optimise_target()
    _OptimiserContainer.CONTAINERS.clear()


def builtins_are_static():
    """
    Promises that the given method does not runtime-override builtins, so we can safely
    eval() them at optimisation time
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        optimiser.code_walkers.append(
            GlobalStaticLookupProcessor(matcher=MetaArgMatcher(_is_builtin_name))
        )
        optimiser.code_walkers.append(
            SideEffectFreeMethodCallRemover()
        )
        optimiser.code_walkers.append(
            EvalAtOptimisationTime()
        )
        return target

    return annotation


def standard_library_is_safe(restriction: str = None):
    """
    Marker that standard library stuff is not touched by the code in an modifying way
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        optimiser.code_walkers.append(
            StandardLibraryResolver(restriction) if restriction is not None else StandardLibraryAllResolver()
        )
        # todo: add these only when not present, otherwise move after this
        optimiser.code_walkers.append(
            StaticObjectAccessorResolver()
        )
        optimiser.code_walkers.append(
            EvalAtOptimisationTime()
        )
        return target

    return annotation


def name_is_static(name: str, accessor: typing.Callable, matcher: AbstractInstructionMatcher = None):
    """
    Marks a certain global name as static
    WARNING: when to the global is written, this will fail to detect that!

    :param name: the global name
    :param accessor: accessor to the static value
    :param matcher: optional, an instruction matcher
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        optimiser.code_walkers.append(
            Global2ConstReplace(name, accessor(), matcher=MetaArgMatcher(_is_builtin_name))
        )
        return target

    return annotation


def returns_argument(index: int = 0):
    """
    Marks a function to return a certain argument
    Can be used in some cases for optimisation
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        return target

    return annotation


def object_method_is_protected(
    name: str,
    accessor: typing.Callable[[], typing.Callable],
    matcher: AbstractInstructionMatcher = None,
):
    """
    Marks that a certain function on an object is known at optimiser time
    Useful when using protected classes / objects, or builtins like lists, dicts, ...

    The optimiser is allowed to add this to calls not marked as they are here

    todo: implement
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        # optimiser.code_walkers.append(StaticMethodLookup(name, accessor(), matcher=matcher))
        return target

    return annotation


def constant_global():
    """
    Marks the method as mutating only the internal state of the class / object, no global
    variables
    This can lead to optimisations into caching globals around the code
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        return target

    return annotation


def constant_arg(name: str):
    """
    Promises that the given arg will not be modified
    Only affects mutable data types
    Removes the need to copy the data during inlining
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        optimiser.constant_args.add(name)
        return target

    return annotation


def forced_arg_type(name: str, type_accessor: typing.Callable, may_subclass=True):
    """
    Marks a certain arg to have that exact type, or a subclass of it when specified
    WARNING: when passing another type, may crash as we do optimisations around that type!

    :param name: the parameter name
    :param type_accessor: the accessor method for the type of the parameter
    :param may_subclass: if subclasses of that type are allowed or not
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        return target

    return annotation


def forced_attribute_type(name: str, type_accessor: typing.Callable[[], typing.Type], may_subclass=False, source_source=None):
    """
    Forced a certain data type on an object attribute
    Not validated, but allows optimisations to happen!

    Can speed up calls by a lot
    """

    def annotation(target: typing.Union[typing.Callable, typing.Type]):
        optimiser = _schedule_optimisation(target)

        if may_subclass:
            pass  # todo: what can we do here?
        elif isinstance(target, typing.Type):
            optimiser.attribute_type_marks[name] = type_accessor()
        else:
            pass  # todo: the function body should also be optimised

        return target

    return annotation


def constant_operation():
    """
    Promises that the method will not affect the state of the system, meaning it is e.g.
    a getter method
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target).is_constant = True
        _schedule_optimisation(target).is_side_effect_free = True
        return target

    return annotation


def cycle_stable_result():
    """
    Similar to constant_global_operation(), but is only constant in one cycle,
    meaning most likely it can only be cached in a single method and its sub-parts
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def mutable_attribute(name: str):
    """
    Marks a certain attribute to be mutable
    Only affects when all_immutable_attributes() is used also on the class
    """

    def annotation(target: typing.Type):
        _schedule_optimisation(target)
        return target

    return annotation


def immutable_attribute(name: str):
    """
    Marks a certain attribute to be immutable
    """

    def annotation(target: typing.Type):
        _schedule_optimisation(target)
        return target

    return annotation


def all_immutable_attributes():
    """
    Marks all attributes to be immutable
    """

    def annotation(target: typing.Type):
        _schedule_optimisation(target)
        return target

    return annotation


def inline_call(
    call_target: str,
    static_target: typing.Callable[[], typing.Callable] = None,
    matcher: AbstractInstructionMatcher = None,
):
    """
    Marks the calls to the given method to be inlined
    The optimiser has the last word on this and may choose
    different ways of optimising this

    'static_target' might be a callable returning a method that represents the target
    The static_target function will be invoked with "self" depending on if it requires it or not
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)  # .code_walkers.append(
        #     MethodInlineProcessor(call_target, static_target)
        # )
        return target

    return annotation


def eval_static(call_target: str):
    """
    Marks the call to the given method as a static eval-ed one
    Useful for configuration values
    Can only be used in some special cases where the arguments of the method call are known at
    optimisation time, e.g. using only constants

    WARNING: the value will be replaced by a static value, which is copy.deepcopy()-ed (when needed)

    The optimiser is allowed to decide to add tis by its own when it encounters a method marked
    as constant
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def eval_instance_static(call_target: str, allow_ahead_of_time=True):
    """
    Marks the call to the given method as a static eval-ed ones for each instance of the class

    Can only be used in some special cases where the arguments of the method call are known at
    optimisation time, e.g. using only constants

    The optimiser may choose to calculate the value of the expression ahead of time for each instance, meaning
    an injection into the constructor. This behaviour can be disabled via allow_ahead_of_time=False
    The injection would happen below most code, if there is no access to the static eval-ed method
    in the constructor itself

    WARNING: the value will be replaced by a static value, which is copy.deepcopy()-ed (when needed)
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def access_static(name: str):
    """
    Accesses a variable (likely a global one) at optimisation time
    and puts it in the bytecode as a constant

    'name' can be a tree like shared.IS_CLIENT
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def access_once(name: str):
    """
    Accesses a variable which may get accessed multiple times only once's and cache the result.
    May move the access as early as possible
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def try_optimise():
    """
    Tries to optimise the given method
    Above annotations will also use this annotation by default
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def assign_local_type(name: str, access: str):
    def annotation(target: typing.Callable):
        module, path = access.split(":")
        module = importlib.import_module(module)

        for e in path.split("."):
            module = getattr(module, e)

        _schedule_optimisation(target).specified_locals[name] = module
        return target

    return annotation


def promise_return_type(access: str):
    def annotation(target: typing.Callable):
        module, path = access.split(":")
        module = importlib.import_module(module)

        for e in path.split("."):
            module = getattr(module, e)

        _schedule_optimisation(target).return_type = module
        return target

    return annotation


def no_internal_cache():
    """
    Marks a class to have no internal cache, meaning if the instance is created and not stored,
    it will be the same as if it was never created in the first place.

    Can be used together with constant_global_operation / constant_operation on methods to
    make optimising more instances away easier.

    Allows to inline certain expressions at optimisation time if the underlying object is only used
    as a calculator
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation
