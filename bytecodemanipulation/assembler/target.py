import typing

import bytecodemanipulation.MutableFunction

import bytecodemanipulation.assembler.Parser

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
        they will be changed into JUMP-TO-END-OF-MACRO!

    :param export_name: the name to export into the global namespace
    """

    def annotation(function):
        from bytecodemanipulation.assembler.Parser import MacroAssembly
        from bytecodemanipulation.assembler.Lexer import IdentifierToken

        macro_name = (export_name or function.__qualname__).replace(".", ":")

        mutable = bytecodemanipulation.MutableFunction.MutableFunction(function)

        macro_asm = MacroAssembly(
            [IdentifierToken(macro_name[-1])],
            [
                # todo: add data type here!
                MacroAssembly.MacroArg(IdentifierToken(name))
                for name in mutable.shared_variable_names[:mutable.argument_count]
            ],
            MacroAssembly.Function2CompoundMapper(function, scoped_names=mutable.shared_variable_names[:mutable.argument_count]),
        )

        namespace = macro_name.split(":")[:-1]

        scope = bytecodemanipulation.assembler.Parser.ParsingScope.create_for_function(function)
        namespace_obj = scope.lookup_namespace(namespace)

        if macro_name.split(":")[-1] not in namespace_obj:
            namespace_obj[macro_name.split(":")[-1]] = MacroAssembly.MacroOverloadPage(macro_name.split(":"))

        namespace_obj[macro_name.split(":")[-1]].add_assembly(macro_asm)

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
