import abc

import typing

from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor
from bytecodemanipulation.assembler.AbstractBase import (
    ParsingScope,
    IAssemblyStructureVisitable,
    AbstractExpression,
)
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import (
    ConstantAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)


class AbstractClassDefinitionAssembly(AbstractAssemblyInstruction, abc.ABC):
    # CLASS <name> '<' <exposed namespace> '>' ['(' [<parent> {',' <parent>}] ')'] '{' ... '}'
    NAME = "CLASS"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractClassDefinitionAssembly":
        name = parser.parse_identifier_like(scope)

        if name is None:
            raise throw_positioned_error(
                scope,
                parser[0],
                "Expected <identifier like>"
            )

        namespace = None

        if opening_bracket := parser.try_consume(SpecialToken("<")):
            # todo: maybe use try_parse_identifier_like() instead
            namespace_f = parser.try_consume(IdentifierToken)

            if namespace_f is None:
                raise throw_positioned_error(
                    scope,
                    parser[0],
                    "<name> expected",
                )

            namespace = [namespace_f.text]

            while parser.try_consume(SpecialToken(":")):
                p = parser.try_consume(IdentifierToken)

                if p is None:
                    raise throw_positioned_error(
                        scope,
                        [namespace_f, parser[0]],
                        "<name> expected after ':' to complete namespace name",
                    )

                namespace.append(p.text)

            if parser.try_consume(SpecialToken(">")) is None:
                raise throw_positioned_error(
                    scope,
                    [opening_bracket, parser[0]],
                    "expected '>' to close namespace declaration",
                )

        parents = []

        if opening_bracket := parser.try_consume(SpecialToken("(")):
            if parent := parser.try_consume_access_to_value():
                parents.append(parent)

                while parser.try_consume(SpecialToken(",")):
                    if parser[0] == SpecialToken(")"):
                        break

                    parent = parser.try_consume_access_to_value()
                    if parent is None:
                        raise throw_positioned_error(
                            scope,
                            parser[0],
                            "Expected <expression> for parent",
                        )

                    parents.append(parent)

            if not parser.try_consume(SpecialToken(")")):
                raise throw_positioned_error(scope, [opening_bracket, parser[0]], "Expected ')'")

        if not parents:
            parents = [ConstantAccessExpression(object)]

        code_block = parser.parse_body(scope=scope, namespace_part=namespace)
        return cls(
            name,
            parents,
            code_block,
        )

    def __init__(
        self, name: IIdentifierAccessor, parents, code_block: CompoundExpression
    ):
        self.name = name
        self.parents = parents
        self.code_block = code_block

    def __repr__(self):
        return f"ClassAssembly::'{self.name}'({','.join(map(repr, self.parents))}){{{self.code_block}}}"

    def copy(self):
        return AbstractClassDefinitionAssembly(
            self.name,
            [parent.copy() for parent in self.parents],
            self.code_block.copy(),
        )

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.name == other.name
            and self.parents == other.parents
            and self.code_block == other.code_block
        )
