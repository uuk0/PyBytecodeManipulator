import abc

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
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
    # CLASS <name> ['(' [<parent> {',' <parent>}] ')'] '{' ... '}'
    NAME = "CLASS"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractClassDefinitionAssembly":
        name_token = parser.consume(IdentifierToken, err_arg=scope)

        parents = []

        if parser.try_consume(SpecialToken("(")):
            if parent := parser.try_consume_access_to_value():
                parents.append(parent)

                while parser.try_consume(SpecialToken(",")):
                    if parser[0] == SpecialToken(")"):
                        break

                    parent = parser.try_consume_access_to_value()
                    if parent is None:
                        raise throw_positioned_syntax_error(
                            scope,
                            parser[0],
                            "Expected <expression>",
                        )
                    parents.append(parent)

            if not parser.try_consume(SpecialToken(")")):
                raise throw_positioned_syntax_error(scope, parser[0], "Expected ')'")

        if not parents:
            parents = [ConstantAccessExpression(object)]

        code_block = parser.parse_body(namespace_part=name_token.text, scope=scope)
        return cls(
            name_token,
            parents,
            code_block,
        )

    def __init__(
        self, name_token: IdentifierToken, parents, code_block: CompoundExpression
    ):
        self.name_token = name_token
        self.parents = parents
        self.code_block = code_block

    def __repr__(self):
        return f"ClassAssembly::'{self.name_token.text}'({','.join(map(repr, self.parents))}){{{self.code_block}}}"

    def copy(self):
        return AbstractClassDefinitionAssembly(
            self.name_token,
            [parent.copy() for parent in self.parents],
            self.code_block.copy(),
        )

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.name_token == other.name_token
            and self.parents == other.parents
            and self.code_block == other.code_block
        )
