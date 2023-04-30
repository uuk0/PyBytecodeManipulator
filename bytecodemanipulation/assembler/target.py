import typing


T = typing.TypeVar("T")


class VARIABLE(typing.Generic[T]):
    pass


class VARIABLE_ARG(typing.Generic[T]):
    pass


class CODE_BLOCK:
    pass


def assembly(code: str):
    raise RuntimeError("Function must be annotated first!")


def label(name: str):
    raise RuntimeError("Function must be annotated first!")


def jump(label_name: str):
    raise RuntimeError("Function must be annotated first!")


def make_macro(export_name: str = None, /):
    """
    Makes the annotated function a macro function, making it possible to use as a macro

    WARNING: the internal system needs to do some clever stuff around parameters, and might reject
    your parameter configuration (this mostly includes keyword arguments)

    To use the macro somewhere else, the target should be also annotated with some processing
    function, and the reference should be static-decidable.
    Otherwise, a call to the real function will be used, and the bytecode of the callee
    will be tried to be modified

    WARNING: returns are currently not allowed in macros!

    :param export_name: the name to export into the global namespace
    """

    def annotation(function):
        from bytecodemanipulation.assembler.Parser import MacroAssembly
        from bytecodemanipulation.assembler.Lexer import IdentifierToken

        macro_asm = MacroAssembly(
            [IdentifierToken(e) for e in export_name.split(":")]
            if export_name
            else [IdentifierToken(function.__name__)],
            [
                MacroAssembly.MacroArg(IdentifierToken(e))
                for e in function.__code__.co_varnems[: function.__code__.co_argcount]
            ],
            MacroAssembly.Function2CompoundMapper(function),
        )

        # todo: store macro assembly into file namespace

        return function

    return annotation


def make_macro_not_callable(target: typing.Callable):
    """
    Makes the target to a macro-only thing, raising a RuntimeError when called directly.

    WARNING: will prevent dynamic inlining from happening
    """
    return target


def configurate_makro_parameter(name: str | int, config_pattern: typing.Type):
    """
    Configures the type of parameter of a @make_macro annotated function

    :param name: the name of the parameter, or the index
    :param config_pattern: the type of parameter
    """

    def annotation(function):
        return function

    return annotation
