import typing


def check_on_function(target: typing.Callable):
    hints = typing.get_type_hints(target)
