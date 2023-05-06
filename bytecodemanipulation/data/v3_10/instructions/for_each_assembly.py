import itertools
import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import AbstractAssemblyInstruction
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.data.shared.expressions.CompoundExpression import CompoundExpression
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class ForEachAssembly(AbstractAssemblyInstruction):
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
    ) -> "ForEachAssembly":
        initial = parser.try_consume_access_to_value()
        if initial is None:
            raise throw_positioned_syntax_error(
                scope,
                parser[0],
                "<expression> expected"
            )
        variables = [initial]


        while parser.try_consume(SpecialToken(",")):

            expr = parser.try_consume_access_to_value()

            if expr is None:
                raise throw_positioned_syntax_error(
                    scope,
                    parser[0],
                    "<expression> expected"
                )

            variables.append(expr)

        if not parser.try_consume(IdentifierToken("IN")):
            raise throw_positioned_syntax_error(
                scope,
                parser[0],
                "'IN' expected"
            )

        source = parser.try_consume_access_to_value()
        if not source:
            raise throw_positioned_syntax_error(
                scope,
                parser[0],
                "<expression> expected"
            )
        sources = [source]

        multi = None
        while parser.try_consume(SpecialToken(",")) or (multi := parser.try_consume(SpecialToken("*"))):
            source = parser.try_consume_access_to_value()
            if not source:
                raise throw_positioned_syntax_error(
                    scope,
                    parser[0],
                    "<expression> expected"
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
                f"Number of Variables ({len(variables)}) must equal number of Sources ({len(sources)})"
            )

        body = parser.parse_body(scope=scope)
        return cls(
            variables,
            sources,
            body,
            scope.last_base_token,
        )

    def __init__(self, variables: typing.List[AbstractSourceExpression], sources: typing.List[AbstractSourceExpression], body: CompoundExpression, base_token: AbstractToken = None):
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
            [
                f"{source} -> {var}"
                for var, source in zip(self.variables, self.sources)
            ]
        )
        return f"FOREACH({entries})"

    def __eq__(self, other):
        return type(self) == type(other) and self.variables == other.variables and self.sources == other.sources and self.body == other.body

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if len(self.variables) != 1:
            bytecode = [
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.LOAD_CONST, zip),
            ]
        else:
            bytecode = []

        for source in self.sources:
            bytecode += source.emit_bytecodes(function, scope)

        loop_label_name_enter = scope.scope_name_generator("foreach_loop_enter")
        loop_label_name_exit = scope.scope_name_generator("foreach_loop_exit")

        if len(self.variables) != 1:
            bytecode += [
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.CALL_FUNCTION, arg=len(self.sources)),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.GET_ITER),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.BYTECODE_LABEL, loop_label_name_enter),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.FOR_ITER, JumpToLabel(loop_label_name_exit)),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.UNPACK_SEQUENCE, arg=len(self.sources)),
            ]
        else:
            bytecode += [
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.GET_ITER),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.BYTECODE_LABEL, loop_label_name_enter),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.FOR_ITER, JumpToLabel(loop_label_name_exit)),
            ]

        for var in self.variables:
            bytecode += var.emit_store_bytecodes(function, scope)

        bytecode += self.body.emit_bytecodes(function, scope)

        bytecode += [
            Instruction.create_with_token(self.base_token, function, -1, Opcodes.JUMP_ABSOLUTE, JumpToLabel(loop_label_name_enter)),
            Instruction.create_with_token(self.base_token, function, -1, Opcodes.BYTECODE_LABEL, loop_label_name_exit),
        ]

        return bytecode
