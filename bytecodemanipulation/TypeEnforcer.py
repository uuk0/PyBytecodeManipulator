import typing

from bytecodemanipulation.MutableFunction import MutableFunction

from bytecodemanipulation.Optimiser import _OptimisationContainer


def check_on_function(target: typing.Callable):
    hints = typing.get_type_hints(target)
    container = _OptimisationContainer.get_for_target(target)
    mutable = MutableFunction(target)
