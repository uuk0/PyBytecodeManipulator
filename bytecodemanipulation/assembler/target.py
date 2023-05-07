import typing

import bytecodemanipulation.assembler.AbstractBase
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


def _raise_macro_direct_call_error():
    raise RuntimeError("Cannot call <macro> with normal call!")


def make_macro(export_name: str = None, /, prevent_direct_calls=False):
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
    :param prevent_direct_calls: if to prevent calls in non-macro form
    """

    def annotation(function):
        from bytecodemanipulation.data.shared.instructions.MacroAssembly import (
            MacroAssembly,
        )
        from bytecodemanipulation.assembler.Lexer import IdentifierToken

        macro_name = (export_name or function.__qualname__).replace(".", ":")

        mutable = bytecodemanipulation.MutableFunction.MutableFunction(function)

        macro_asm = MacroAssembly(
            [IdentifierToken(macro_name[-1])],
            [
                # todo: add data type here!
                MacroAssembly.MacroArg(IdentifierToken(name))
                for name in mutable.shared_variable_names[: mutable.argument_count]
            ],
            MacroAssembly.Function2CompoundMapper(
                function,
                scoped_names=mutable.shared_variable_names[: mutable.argument_count],
            ),
        )

        namespace = macro_name.split(":")[:-1]

        scope = bytecodemanipulation.assembler.AbstractBase.ParsingScope.create_for_function(
            function
        )
        namespace_obj = scope.lookup_namespace(namespace)

        if macro_name.split(":")[-1] not in namespace_obj:
            namespace_obj[macro_name.split(":")[-1]] = MacroAssembly.MacroOverloadPage(
                macro_name.split(":")
            )

        namespace_obj[macro_name.split(":")[-1]].add_assembly(macro_asm)

        if prevent_direct_calls:
            mutable.copy_from(
                bytecodemanipulation.MutableFunction.MutableFunction(
                    _raise_macro_direct_call_error
                )
            )
            mutable.reassign_to_function()

        return function

    return annotation


def configurate_makro_parameter(name: str | int, config_pattern: typing.Type):
    """
    Configures the type of parameter of a @make_macro annotated function

    :param name: the name of the parameter, or the index
    :param config_pattern: the type of parameter
    """

    def annotation(function):
        return function

    return annotation


def apply_operations(target: typing.Callable):
    from bytecodemanipulation.MutableFunction import MutableFunction
    from bytecodemanipulation.assembler.Emitter import apply_inline_assemblies

    mutable = MutableFunction(target)
    apply_inline_assemblies(mutable)
    mutable.reassign_to_function()
    return target
