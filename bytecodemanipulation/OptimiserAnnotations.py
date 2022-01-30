import builtins
import importlib
import types
import typing

from . import CodeOptimiser
from bytecodemanipulation.InstructionMatchers import AbstractInstructionMatcher
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.BytecodeProcessors import (
    AbstractBytecodeProcessor,
    MethodInlineProcessor,
    Global2ConstReplace,
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
        if isinstance(self.target, types.FunctionType):
            self.optimise_method(self.target)
        else:
            for value in self.target.__dict__.values():
                if isinstance(value, types.FunctionType):
                    self.optimise_method(value)

    def optimise_method(self, target):
        helper = BytecodePatchHelper(target)

        for processor in self.code_walkers:
            print(f"[INFO] applying optimiser transformer {processor} onto {target}")
            processor.apply(None, helper.patcher, helper)
            helper.re_eval_instructions()

        optimise_code(helper)

        helper.store()
        helper.patcher.applyPatches()
        CodeOptimiser.optimise_code(helper)

    async def optimize_target_async(self):
        try:
            self.optimise_target()
        except:
            print(self.target)
            raise


def _schedule_optimisation(
    target: typing.Union[typing.Callable, typing.Type],
) -> _OptimiserContainer:
    if not hasattr(target, "optimiser_container"):
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
    WARNING: when passing another type, will crash as we do optimisations around that type

    :param name: the parameter name
    :param type_accessor: the accessor method for the type of the parameter
    :param may_subclass: if subclasses of that type are allowed or not
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        return target

    return annotation


def constant_operation():
    """
    Promises that the method will not affect the state of the system, meaning it is e.g.
    a getter method
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target).is_constant = True
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
