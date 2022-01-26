import importlib
import typing

from . import CodeOptimiser
from bytecodemanipulation.InstructionMatchers import AbstractInstructionMatcher
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.BytecodeProcessors import (
    AbstractBytecodeProcessor,
    MethodInlineProcessor,
)


class _OptimiserContainer:
    CONTAINERS: typing.List["_OptimiserContainer"] = []

    def __init__(self, target):
        self.target = target
        self.is_constant = False
        self.constant_args: typing.Set[str] = set()
        self.code_walkers: typing.List[AbstractBytecodeProcessor] = []
        self.specified_locals: typing.Dict[str, typing.Type] = {}
        self.return_type: typing.Optional[typing.Type] = None

    def optimise_target(self):
        if isinstance(self.target, typing.Callable):
            helper = BytecodePatchHelper(self.target)

            for processor in self.code_walkers:
                print(f"[INFO] applying optimiser mixin {processor} onto {self.target}")
                processor.apply(None, helper.patcher, helper)
                helper.re_eval_instructions()

            helper.store()

            CodeOptimiser.optimise_code(helper)

    async def optimize_target_async(self):
        try:
            self.optimise_target()
        except:
            print(self.target)
            raise


def _schedule_optimisation(
    target: typing.Callable | typing.Type,
) -> _OptimiserContainer:
    if not hasattr(target, "optimiser_container"):
        target.optimiser_container = _OptimiserContainer(target)
        _OptimiserContainer.CONTAINERS.append(target.optimiser_container)

    return target.optimiser_container


def run_optimisations():
    for instance in _OptimiserContainer.CONTAINERS:
        instance.optimise_target()


def builtins_are_static():
    """
    Promises that the given method does not runtime-override builtins, so we can safely
    eval() them at optimisation time
    """

    def annotation(target: typing.Callable):
        optimiser = _schedule_optimisation(target)
        # optimiser.code_walkers.append()
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


def constant_operation():
    """
    Promises that the method will not affect the state of the system, meaning it is e.g.
    a getter method
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target).is_constant = True
        return target

    return annotation


def constant_global_operation():
    """
    Promises the function modifies only the internal state of the object, not anything else,
    including the class body
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def cycle_stable_result():
    """
    Similar to constant_global_operation(), but is only constant in one cycle (a tick),
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


def constant_global():
    """
    Marks the method as mutating only the internal state of the class / object, no global
    variables
    This can lead to optimisations into caching globals around the code
    """

    def annotation(target: typing.Callable):
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

    WARNING: the value will be replaced by a static value, which is copy.deepcopy()-ed (when needed)
    """

    def annotation(target: typing.Callable):
        _schedule_optimisation(target)
        return target

    return annotation


def invalidate_cache(function, call_target: str, obj=None):
    pass


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
