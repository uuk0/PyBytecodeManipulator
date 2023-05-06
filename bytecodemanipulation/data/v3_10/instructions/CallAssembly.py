import functools
import typing

from bytecodemanipulation.data.shared.instructions.CallAssembly import (
    AbstractCallAssembly,
)
from bytecodemanipulation.data.shared.expressions.MacroAccessExpression import (
    MacroAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.MacroAssembly import MacroAssembly
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class CallAssembly(AbstractCallAssembly):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.is_macro:
            return self.emit_macro_bytecode(function, scope)

        has_seen_star = False
        has_seen_star_star = False
        has_seen_kw_arg = False

        for arg in self.args:
            if isinstance(arg, CallAssembly.KwArg):
                has_seen_kw_arg = True

            elif isinstance(arg, CallAssembly.KwArgStar):
                has_seen_star_star = True

            elif isinstance(arg, CallAssembly.StarArg):
                has_seen_star = True

        if not has_seen_kw_arg and not has_seen_star and not has_seen_star_star:
            if self.is_partial:
                bytecode = [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial)
                ]
                extra_args = 1
            else:
                bytecode = []
                extra_args = 0

            bytecode += self.call_target.emit_bytecodes(function, scope)

            for arg in self.args:
                bytecode += arg.source.emit_bytecodes(function, scope)

            bytecode += [
                Instruction(
                    function, -1, "CALL_FUNCTION", arg=len(self.args) + extra_args
                ),
            ]

        elif has_seen_kw_arg and not has_seen_star and not has_seen_star_star:
            if self.is_partial:
                bytecode = [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial)
                ]
                extra_args = 1
            else:
                bytecode = []
                extra_args = 0

            bytecode += self.call_target.emit_bytecodes(function, scope)

            kw_arg_keys = []

            for arg in reversed(self.args):
                bytecode += arg.source.emit_bytecodes(function, scope)

                if isinstance(arg, CallAssembly.KwArg):
                    kw_arg_keys.append(arg.key.text)

                kw_const = tuple(reversed(kw_arg_keys))

                bytecode += [
                    Instruction(function, -1, "LOAD_CONST", kw_const),
                    Instruction(
                        function,
                        -1,
                        "CALL_FUNCTION_KW",
                        arg=len(self.args) + extra_args,
                    ),
                ]

        else:
            bytecode = self.call_target.emit_bytecodes(function, scope)

            bytecode += [Instruction(function, -1, "BUILD_LIST", arg=0)]

            if self.is_partial:
                bytecode += [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial),
                    Instruction(function, -1, "LIST_APPEND"),
                ]

            i = -1
            for i, arg in enumerate(self.args):
                bytecode += arg.source.emit_bytecodes(function, scope)

                if isinstance(arg, CallAssembly.Arg):
                    bytecode += [Instruction(function, -1, "LIST_APPEND", arg=1)]
                elif isinstance(arg, CallAssembly.StarArg):
                    bytecode += [Instruction(function, -1, "LIST_EXTEND", arg=1)]
                else:
                    break

            bytecode += [
                Instruction(function, -1, "LIST_TO_TUPLE"),
            ]

            if has_seen_kw_arg or has_seen_star_star:
                bytecode += [Instruction(function, -1, "BUILD_MAP", arg=0)]

                for arg in self.args[i + 1 :]:
                    if isinstance(arg, CallAssembly.KwArg):
                        bytecode += (
                            [Instruction(function, -1, "LOAD_CONST", arg.key.text)]
                            + arg.source.emit_bytecodes(function, scope)
                            + [
                                Instruction(function, -1, "BUILD_MAP", arg=1),
                                Instruction(function, -1, "DICT_MERGE", arg=1),
                            ]
                        )
                    else:
                        bytecode += arg.source.emit_bytecodes(function, scope) + [
                            Instruction(function, -1, "DICT_MERGE", arg=1)
                        ]

            bytecode += [
                Instruction(
                    function,
                    -1,
                    "CALL_FUNCTION_EX",
                    arg=int(has_seen_kw_arg or has_seen_star_star),
                ),
            ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)

        return bytecode

    def emit_macro_bytecode(self, function: MutableFunction, scope: ParsingScope):
        access = typing.cast(MacroAccessExpression, self.call_target)
        name = access.name

        macro_declaration = scope.lookup_name_in_scope(name[0].text)

        if macro_declaration is None:
            raise throw_positioned_syntax_error(
                scope,
                typing.cast(MacroAccessExpression, self.call_target).name,
                f"Macro '{':'.join(map(lambda e: e.text, name))}' not found!",
                NameError,
            )

        if len(name) > 1:
            for e in name[1:]:
                macro_declaration = macro_declaration[e.text]

        if not isinstance(macro_declaration, MacroAssembly.MacroOverloadPage):
            raise RuntimeError(
                f"Expected Macro Declaration for '{':'.join(map(lambda e: e.text, name))}', got {macro_declaration}"
            )

        macro, args = macro_declaration.lookup([arg.source for arg in self.args], scope)

        if self.target is not None and macro.return_type is None:
            raise RuntimeError(
                f"Expected <return type> declaration at macro if using '->' in call"
            )

        bytecode = macro.emit_call_bytecode(function, scope, args)

        if self.target:
            bytecode += self.target.emit_bytecodes(function, scope)

        return bytecode
