import typing
from abc import ABC

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.data.shared.expressions.MacroAccessExpression import (
    MacroAccessExpression,
)
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


class AbstractCallAssembly(AbstractAssemblyInstruction, AbstractAccessExpression, ABC):
    # CALL ['PARTIAL' | 'MACRO'] <call target> (<args>) [-> <target>]
    NAME = "CALL"

    class IArg(AbstractAccessExpression, ABC):
        """
        Abstract base class for argument-like for calls
        Nothing is abstract, but most requires a special subclass
        """

        __slots__ = ("source", "is_dynamic")

        def __init__(
            self,
            source: typing.Union["AbstractAccessExpression", IdentifierToken],
            is_dynamic: bool = False,
        ):
            self.source = source
            self.is_dynamic = is_dynamic

        def __repr__(self):
            return f"{type(self).__name__}{'' if not self.is_dynamic else 'Dynamic'}({self.source})"

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.source == other.source
                and self.is_dynamic == other.is_dynamic
            )

        def copy(self) -> "AbstractCallAssembly.IArg":
            return type(self)(self.source.copy(), self.is_dynamic)

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
            parents: list,
        ):
            return visitor(
                self, (self.source.visit_parts(visitor, parents + [self]),), parents
            )

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            return self.source.emit_bytecodes(function, scope)

        def emit_store_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            return self.source.emit_store_bytecodes(function, scope)

    class Arg(IArg):
        pass

    class StarArg(IArg):
        pass

    class KwArg(IArg):
        __slots__ = ("key", "source", "is_dynamic")

        def __init__(
            self,
            key: IdentifierToken | str,
            source: typing.Union["AbstractAccessExpression", IdentifierToken],
            is_dynamic: bool = False,
        ):
            self.key = key if isinstance(key, IdentifierToken) else IdentifierToken(key)
            super().__init__(source, is_dynamic=is_dynamic)

        def __repr__(self):
            return f"{type(self).__name__}{'' if not self.is_dynamic else 'Dynamic'}({self.key.text} = {self.source})"

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.source == other.source
                and self.key == other.key
                and self.is_dynamic == other.is_dynamic
            )

        def copy(self):
            return type(self)(self.key, self.source.copy(), self.is_dynamic)

    class KwArgStar(IArg):
        pass

    @classmethod
    def construct_from_partial(
        cls, access: AbstractAccessExpression, parser: "Parser", scope: ParsingScope
    ) -> "AbstractCallAssembly":
        """
        Constructs an CallAssembly from an already parsed access expression.
        Used by the Parser when parsing an call as a expression to be used inline
        """
        return cls.consume_inner(
            parser, False, False, scope, call_target=access, allow_target=False
        )

    @classmethod
    def consume_macro_call(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractCallAssembly":
        """
        Consumes a call to a macro
        Used by the Parser when finding macros to be used like assembly instructions
        """
        return cls.consume_inner(parser, False, True, scope)

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractCallAssembly":
        """
        The normal consumer for the instruction
        Optionally consumes the PARTIAL and MACRO prefixes
        """
        is_partial = bool(parser.try_consume(IdentifierToken("PARTIAL")))
        is_macro = not is_partial and bool(parser.try_consume(IdentifierToken("MACRO")))
        return cls.consume_inner(parser, is_partial, is_macro, scope)

    @classmethod
    def consume_inner(
        cls,
        parser: "Parser",
        is_partial: bool,
        is_macro: bool,
        scope: ParsingScope,
        call_target=None,
        allow_target=True,
    ) -> "AbstractCallAssembly":
        """
        The real consumer, configurable to parse special parts
        """
        if call_target is None:
            if not is_macro:
                call_target = parser.try_parse_data_source(
                    include_bracket=False, scope=scope, allow_calls=False
                )

                if isinstance(call_target, AbstractCallAssembly):
                    raise RuntimeError

            else:
                name = [parser.consume(IdentifierToken, err_arg=scope)]

                while parser.try_consume(SpecialToken(":")):
                    name.append(parser.consume(IdentifierToken, err_arg=scope))

                call_target = MacroAccessExpression(name)

        if call_target is None:
            raise throw_positioned_syntax_error(
                scope,
                parser.try_inspect(),
                "expected <expression> to be called (did you forget the prefix?)"
                if not is_macro
                else "expected <macro name>",
            )

        args: typing.List[AbstractCallAssembly.IArg] = []

        parser.consume(SpecialToken("("), err_arg=scope)

        has_seen_keyword_arg = False

        while not (bracket := parser.try_consume(SpecialToken(")"))):
            if (
                isinstance(parser[0], IdentifierToken)
                and parser[1] == SpecialToken("=")
                and not is_macro
            ):
                key = parser.consume(IdentifierToken)
                parser.consume(SpecialToken("="))

                is_dynamic = is_partial and bool(parser.try_consume(SpecialToken("?")))

                expr = parser.try_parse_data_source(
                    allow_primitives=True, include_bracket=False
                )

                args.append(AbstractCallAssembly.KwArg(key, expr, is_dynamic))

                has_seen_keyword_arg = True

            elif parser[0].text == "*" and not is_macro:
                if parser[1] == SpecialToken("*"):
                    parser.consume(SpecialToken("*"))
                    parser.consume(SpecialToken("*"))
                    expr = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False
                    )
                    args.append(AbstractCallAssembly.KwArgStar(expr))
                    has_seen_keyword_arg = True

                elif not has_seen_keyword_arg:
                    parser.consume(SpecialToken("*"))
                    expr = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False
                    )
                    args.append(AbstractCallAssembly.StarArg(expr))

                else:
                    raise throw_positioned_syntax_error(
                        scope,
                        parser.try_inspect(),
                        "*<arg> only allowed before keyword arguments!",
                    )

            elif not has_seen_keyword_arg:
                if is_macro and parser[0] == SpecialToken("{"):
                    expr = parser.parse_body(scope=scope)
                    is_dynamic = False
                else:
                    is_dynamic = is_partial and bool(
                        parser.try_consume(SpecialToken("?"))
                    )

                    expr = parser.try_consume_access_to_value(allow_primitives=True)

                    if expr is None:
                        if parser[0] == SpecialToken(")"):
                            break

                        raise throw_positioned_syntax_error(
                            scope, parser[0], "<expression> expected"
                        )

                args.append(AbstractCallAssembly.Arg(expr, is_dynamic))

            else:
                raise throw_positioned_syntax_error(
                    scope,
                    parser.try_inspect(),
                    "pure <arg> only allowed before keyword arguments",
                )

            if not parser.try_consume(SpecialToken(",")):
                break

        if bracket is None and not parser.try_consume(SpecialToken(")")):
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected ')'"
            )

        if allow_target and parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(call_target, args, target, is_partial, is_macro)

    def __init__(
        self,
        call_target: AbstractSourceExpression,
        args: typing.List["AbstractCallAssembly.IArg"],
        target: AbstractAccessExpression | None = None,
        is_partial: bool = False,
        is_macro: bool = False,
    ):
        self.call_target = call_target
        self.args = args
        self.target = target
        self.is_partial = is_partial
        self.is_macro = is_macro

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self,
            (
                self.call_target.visit_parts(
                    visitor,
                    parents + [self],
                ),
                [
                    arg.visit_parts(
                        visitor,
                        parents + [self],
                    )
                    for arg in self.args
                ],
                self.target.visit_parts(
                    visitor,
                    parents + [self],
                )
                if self.target
                else None,
            ),
            parents,
        )

    def copy(self) -> "AbstractCallAssembly":
        return type(self)(
            self.call_target.copy(),
            [arg.copy() for arg in self.args],
            self.target.copy() if self.target else None,
            self.is_partial,
            self.is_macro,
        )

    def __repr__(self):
        return f"CALL{('' if not self.is_macro else '-MACRO') if not self.is_partial else '-PARTIAL'}({self.call_target}, ({repr(self.args)[1:-1]}){', ' + repr(self.target) if self.target else ''})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.call_target == other.call_target
            and self.args == other.args
            and self.target == other.target
            and self.is_partial == other.is_partial
            and self.is_macro == other.is_macro
        )
