import abc
import itertools
import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)


class AbstractForEachAssembly(AbstractAssemblyInstruction, abc.ABC):
    # FOREACH <variable> {',' <variable>} IN <iterable> {(',' | '*') <iterable>} '{' <block> '}'
    NAME = "FOREACH"

    class ForEachMultiplier(AbstractAccessExpression):
        def __init__(self, *items: AbstractAccessExpression):
            self.items = list(items)

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            bytecode = [
                Instruction(function, -1, Opcodes.LOAD_CONST, itertools.product),
            ]

            for item in self.items:
                bytecode += item.emit_bytecodes(function, scope)

            bytecode += [
                Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=len(self.items)),
            ]
            return bytecode

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractForEachAssembly":
        initial = parser.try_consume_access_to_value()
        if initial is None:
            raise throw_positioned_syntax_error(
                scope, parser[0], "<expression> expected"
            )
        variables = [initial]

        while parser.try_consume(SpecialToken(",")):

            expr = parser.try_consume_access_to_value()

            if expr is None:
                raise throw_positioned_syntax_error(
                    scope, parser[0], "<expression> expected"
                )

            variables.append(expr)

        if not parser.try_consume(IdentifierToken("IN")):
            raise throw_positioned_syntax_error(scope, parser[0], "'IN' expected")

        source = parser.try_consume_access_to_value()
        if not source:
            raise throw_positioned_syntax_error(
                scope, parser[0], "<expression> expected"
            )
        sources = [source]

        multi = None
        while parser.try_consume(SpecialToken(",")) or (
            multi := parser.try_consume(SpecialToken("*"))
        ):
            source = parser.try_consume_access_to_value()
            if not source:
                raise throw_positioned_syntax_error(
                    scope, parser[0], "<expression> expected"
                )

            if multi:
                s = sources[-1]

                if isinstance(s, cls.ForEachMultiplier):
                    s.items.append(source)
                else:
                    sources[-1] = cls.ForEachMultiplier(s, source)

                multi = None
            else:
                sources.append(source)

        if len(variables) != len(sources):
            raise throw_positioned_syntax_error(
                scope,
                scope.last_base_token,
                f"Number of Variables ({len(variables)}) must equal number of Sources ({len(sources)})",
            )

        body = parser.parse_body(scope=scope)
        return cls(
            variables,
            sources,
            body,
            scope.last_base_token,
        )

    def __init__(
        self,
        variables: typing.List[AbstractAccessExpression],
        sources: typing.List[AbstractAccessExpression],
        body: CompoundExpression,
        base_token: IdentifierToken,
    ):
        self.variables = variables
        self.sources = sources
        self.body = body
        self.base_token = base_token

    def copy(self):
        return type(self)(
            [var.copy() for var in self.variables],
            [source.copy() for source in self.sources],
            self.body.copy(),
        )

    def __repr__(self):
        entries = ", ".join(
            [f"{source} -> {var}" for var, source in zip(self.variables, self.sources)]
        )
        return f"FOREACH({entries})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.variables == other.variables
            and self.sources == other.sources
            and self.body == other.body
        )
