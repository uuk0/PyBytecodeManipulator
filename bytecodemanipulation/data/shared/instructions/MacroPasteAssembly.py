import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import (
    PropagatingCompilerException,
    TraceInfo,
)
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.data.shared.expressions.MacroParameterAcessExpression import (
    MacroParameterAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class MacroPasteAssembly(AbstractAssemblyInstruction):
    # MACRO_PASTE <macro param name> ['[' <access> {',' <access>} ']'] ['->' <target>]
    NAME = "MACRO_PASTE"

    @classmethod
    def register(cls):
        Parser.register(cls)

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "MacroPasteAssembly":
        # Parse an optional § infront of the name
        parser.try_consume(SpecialToken("&"))

        name = parser.consume(IdentifierToken)

        dynamic_names: typing.List[typing.Tuple[AbstractAccessExpression, bool]] = []
        if opening_bracket := parser.try_consume(SpecialToken("[")):
            while parser.try_inspect() != SpecialToken("]"):
                is_static = bool(parser.try_consume(SpecialToken("!")))
                base = parser.try_consume_access_to_value(scope=scope)

                if base is None:
                    raise PropagatingCompilerException(
                        "Expected <expression> after '[' for dynamic name access"
                    ).add_trace_level(
                        scope.get_trace_info().with_token(opening_bracket, parser[0])
                    )

                dynamic_names.append((base, is_static))

                if not parser.try_consume(SpecialToken(",")):
                    break

            if not parser.try_consume(SpecialToken("]")):
                raise PropagatingCompilerException(
                    "expected ']' to close '[' closing dynamic names"
                ).add_trace_level(
                    scope.get_trace_info().with_token(opening_bracket, parser[0])
                )

        if parser.try_consume_multi([SpecialToken("-"), SpecialToken(">")]):
            target = parser.try_consume_access_to_value(
                allow_primitives=False, scope=scope
            )
        else:
            target = None

        return cls(
            name, target, dynamic_names=dynamic_names, trace_info=scope.get_trace_info()
        )

    def __init__(
        self,
        name: IdentifierToken,
        target: AbstractAccessExpression = None,
        dynamic_names: typing.List[typing.Tuple[AbstractAccessExpression, bool]] = None,
        trace_info: TraceInfo = None,
    ):
        self.name = name
        self.target = target
        self.dynamic_names = dynamic_names or []
        self.trace_info = trace_info

    def __repr__(self):
        return f"MACRO_PASTE({self.name.text}{repr(self.dynamic_names)[1:-1]}{'' if self.target is None else '-> '+repr(self.target)})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name == other.name
            and self.target == other.target
            and self.dynamic_names == other.dynamic_names
        )

    def copy(self) -> "MacroPasteAssembly":
        return type(self)(
            self.name,
            self.target.copy() if self.target else None,
            [(e[0].copy(), e[1]) for e in self.dynamic_names],
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        try:
            deref_name = scope.lookup_macro_parameter(self.name.text)

            level = 0
            while isinstance(deref_name, MacroParameterAccessExpression):
                deref_name = scope.lookup_macro_parameter(
                    deref_name.name(scope), start=level
                )
                level += 1

        except KeyError:
            deref_name = None

        if deref_name and hasattr(deref_name, "emit_bytecodes"):
            body: CompoundExpression = deref_name

            if not isinstance(body, CompoundExpression):
                raise PropagatingCompilerException(
                    f"invalid body, got {body}"
                ).add_trace_level(self.trace_info.with_token(self.name))

            instructions = body.emit_bytecodes(function, scope)

            sources = [e(scope) for e in getattr(body, "to_be_stored_at", [])]

            if len(sources) != len(self.dynamic_names):
                raise PropagatingCompilerException(
                    f"expected exactly {len(sources)} parameters at MACRO_PASTE, but got {len(self.dynamic_names)}",
                ).add_trace_level(self.trace_info.with_token(self.name))

            result = []
            special_names = []

            for i, (code, is_static) in enumerate(self.dynamic_names):
                if is_static:
                    label_name = scope.scope_name_generator(f"dynamic_name_{i}")

                    result += code.emit_bytecodes(function, scope)
                    result += [Instruction(Opcodes.STORE_FAST, label_name)]
                    special_names.append(label_name)
                else:
                    special_names.append(None)

            for instr in instructions:
                if instr.has_local():
                    local: str = typing.cast(str, instr.arg_value)

                    if local in sources:
                        index = sources.index(local)
                        code, is_static = self.dynamic_names[index]

                        if instr.opcode == Opcodes.LOAD_FAST:
                            if is_static:
                                result += [
                                    Instruction(
                                        Opcodes.LOAD_FAST, special_names[index]
                                    ),
                                ]
                            else:
                                result += code.emit_bytecodes(function, scope)

                        elif instr.opcode == Opcodes.STORE_FAST:
                            if is_static:
                                raise PropagatingCompilerException(
                                    f"macro parameter {self.name.text} is marked as static, but it was tried to write to"
                                ).add_trace_level(self.trace_info.with_token(self.name))

                            result += code.emit_store_bytecodes(function, scope)
                        else:
                            result.append(instr)

                    elif local.startswith("|"):
                        instr.change_arg_value(local[1:])
                        result.append(instr)
                    else:
                        instr.change_arg_value(":" + local)
                        result.append(instr)
                else:
                    result.append(instr)

            return result + (
                []
                if self.target is None
                else self.target.emit_store_bytecodes(function, scope)
            )

        return [Instruction(Opcodes.MACRO_PARAMETER_EXPANSION, self.name.text)] + (
            []
            if self.target is None
            else self.target.emit_store_bytecodes(function, scope)
        )
