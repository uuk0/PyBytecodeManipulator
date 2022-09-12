import functools
import inspect
import typing


def _is_parent_of(obj, possible_parent: typing.Type) -> bool:
    if isinstance(obj, staticmethod):
        obj = obj.__func__
    if inspect.getfile(obj) != inspect.getfile(possible_parent): return False
    return obj.__qualname__.startswith(possible_parent.__qualname__+".")


