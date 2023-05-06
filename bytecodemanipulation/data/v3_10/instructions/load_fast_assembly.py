import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.Parser import AbstractAssemblyInstruction
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.assembler.util.tokenizer import IntegerToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


@Parser.register
class LoadFastAssembly(AbstractAssemblyInstruction):
    # LOAD_FAST <name> [-> <target>]
    NAME = "LOAD_FAST"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "LoadFastAssembly":
        parser.try_consume(SpecialToken("$"))
        name = parser.consume([IdentifierToken, IntegerToken])

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(name, target)

    def __init__(
        self,
        name_token: IdentifierToken | IntegerToken | str | int,
        target: AbstractAccessExpression | None = None,
    ):
        self.name_token = (
            name_token
            if not isinstance(name_token, (str, int))
            else (
                IdentifierToken(name_token)
                if isinstance(name_token, str)
                else IntegerToken(str(name_token))
            )
        )
        self.target = target

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name_token == other.name_token
            and self.target == other.target
        )

    def __repr__(self):
        return f"LOAD_GLOBAL({self.name_token}{', ' + repr(self.target) if self.target else ''})"

    def copy(self) -> "LoadFastAssembly":
        return LoadFastAssembly(self.name_token, self.target)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_FAST", value)] + (
            self.target.emit_bytecodes(function, scope) if self.target else []
        )

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.target.visit_parts(visitor) if self.target else None,)
        )
