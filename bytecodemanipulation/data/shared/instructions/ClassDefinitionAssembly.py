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
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException, TraceInfo
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
            raise PropagatingCompilerException(
                "expected <identifier-like> after CLASS"
            ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        namespace = None

        if opening_bracket := parser.try_consume(SpecialToken("<")):
            # todo: maybe use try_parse_identifier_like() instead
            namespace_f = parser.try_consume(IdentifierToken)

            if namespace_f is None:
                raise PropagatingCompilerException(
                    "expected <name> after '<' declaring the namespace"
                ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

            namespace = [namespace_f.text]

            while parser.try_consume(SpecialToken(":")):
                p = parser.try_consume(IdentifierToken)

                if p is None:
                    raise PropagatingCompilerException(
                        "expected <name> after ':' to complete namespace name"
                    ).add_trace_level(scope.get_trace_info().with_token(namespace_f, parser[0]))

                namespace.append(p.text)

            if parser.try_consume(SpecialToken(">")) is None:
                raise PropagatingCompilerException(
                    "expected '>' to close namespace declaration"
                ).add_trace_level(scope.get_trace_info().with_token(opening_bracket, parser[0]))

        parents = []

        if opening_bracket := parser.try_consume(SpecialToken("(")):
            if parent := parser.try_consume_access_to_value():
                parents.append(parent)

                while parser.try_consume(SpecialToken(",")):
                    if parser[0] == SpecialToken(")"):
                        break

                    parent = parser.try_consume_access_to_value()
                    if parent is None:
                        raise PropagatingCompilerException(
                            "expected <expression> for parent after '(' or ','"
                        ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

                    parents.append(parent)

            if not parser.try_consume(SpecialToken(")")):
                raise PropagatingCompilerException(
                    "expected ')' closing '(' for parent declaration"
                ).add_trace_level(scope.get_trace_info().with_token(opening_bracket, parser[0]))

        if not parents:
            parents = [ConstantAccessExpression(object)]

        try:
            code_block = parser.parse_body(scope=scope, namespace_part=namespace)
        except PropagatingCompilerException as e:
            e.add_trace_level(scope.get_trace_info().with_token(list(name.get_tokens())), message=f"during parsing class '{name(scope)}'")
            raise e

        return cls(
            name,
            parents,
            code_block,
            trace_info=scope.get_trace_info().with_token(list(name.get_tokens())),
        )

    def __init__(
        self, name: IIdentifierAccessor, parents, code_block: CompoundExpression, trace_info: TraceInfo = None
    ):
        self.name = name
        self.parents = parents
        self.code_block = code_block
        self.trace_info = trace_info

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
