import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.AbstractBase import StaticIdentifier
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.instructions.CallAssembly import (
    AbstractCallAssembly,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression


class AbstractFunctionDefinitionAssembly(AbstractAssemblyInstruction, abc.ABC):
    # DEF [<func name>] ['<' ['!'] <bound variables> '>'] '(' <signature> ')' ['->' <target>] '{' <body> '}'
    NAME = "DEF"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractFunctionDefinitionAssembly":
        prefix = ""

        while parser.try_consume(SpecialToken("|")):
            prefix += "|"

        if prefix == "":
            while parser.try_consume(SpecialToken(":")):
                prefix += ":"

        func_name = parser.parse_identifier_like(scope)

        bound_variables: typing.List[typing.Tuple[IIdentifierAccessor, bool]] = []
        args = []

        if parser.try_consume(SpecialToken("<")):
            is_static = bool(parser.try_consume(SpecialToken("!")))

            expr = parser.try_parse_identifier_like()

            if expr:
                bound_variables.append((expr, is_static))

                while True:
                    if not parser.try_consume(SpecialToken(",")) or not (
                        expr := parser.try_parse_identifier_like()
                    ):
                        break

                    bound_variables.append((expr, is_static))

            parser.consume(SpecialToken(">"), err_arg=scope)

        if (opening_bracket := parser.try_consume(SpecialToken("("))) is None:
            raise throw_positioned_error(
                scope,
                parser[0],
                "expected '(' after <identifier>"
            )

        while parser.try_inspect() != SpecialToken(")"):
            arg = None

            star = parser.try_consume(SpecialToken("*"))
            star_star = parser.try_consume(SpecialToken("*"))
            identifier = parser.try_parse_identifier_like()

            if not identifier:
                if star:
                    raise throw_positioned_error(
                        scope,
                        [star, star_star],
                        "Expected <identifier> after '*'"
                        if not star_star
                        else "Expected <identifier> after '**'",
                    )

                break

            if not star:
                if equal_sign := parser.try_consume(SpecialToken("=")):
                    default_value = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False, allow_op=True
                    )

                    if default_value is None:
                        raise throw_positioned_error(
                            scope,
                            [identifier, equal_sign, parser[0]],
                            "expected <expression>",
                        )

                    arg = AbstractCallAssembly.KwArg(identifier, default_value, token=identifier)

            if not arg:
                if star_star:
                    arg = AbstractCallAssembly.KwArgStar(identifier, token=identifier)

                elif star:
                    arg = AbstractCallAssembly.StarArg(identifier, token=identifier)

                else:
                    arg = AbstractCallAssembly.Arg(identifier, token=identifier)

            args.append(arg)

            if not parser.try_consume(SpecialToken(",")):
                break

        if not parser.try_consume(SpecialToken(")")):
            raise throw_positioned_error(
                scope,
                [opening_bracket, parser[0]],
                "expected ')' matching '(' in function definition",
            )

        if expr := parser.try_consume(SpecialToken("<")):
            if bound_variables:
                raise throw_positioned_error(
                    scope,
                    expr,
                    "got '<' after '(' ... ')' expression, where a '{' ... '}' (code block) was expected"
                )

            raise throw_positioned_error(
                scope,
                expr,
                "Respect ordering (got 'args' before 'captured'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }",
            )

        if (arrow_0 := parser.try_consume(SpecialToken("-"))) and (arrow_1 := parser.try_consume(
            SpecialToken(">")
        )):
            target = parser.try_consume_access_to_value(scope=scope)

            if target is None:
                raise throw_positioned_error(
                    scope,
                    [arrow_0, arrow_1, parser[0]],
                    "expected <expression> after '->' as target"
                )

        elif arrow_0:
            raise throw_positioned_error(
                scope,
                [arrow_0, parser[0]],
                "expected '>' after '-' to complete <target> expression",
            )

        else:
            target = None

        body = parser.parse_body(scope=scope)

        if expr := parser.try_consume(SpecialToken("-")):
            raise throw_positioned_error(
                scope,
                expr,
                "Respect ordering (got 'code' before 'target'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }",
            )

        return cls(func_name, bound_variables, args, body, target, prefix=prefix)

    def __init__(
        self,
        func_name: IIdentifierAccessor | str | None,
        bound_variables: typing.List[typing.Tuple[IIdentifierAccessor, bool] | str],
        args: typing.List[AbstractCallAssembly.IArg],
        body: CompoundExpression,
        target: AbstractAccessExpression | None = None,
        prefix="",
    ):
        self.func_name = (
            func_name if not isinstance(func_name, str) else StaticIdentifier(func_name)
        )
        self.bound_variables: typing.List[typing.Tuple[IIdentifierAccessor, bool]] = []
        # var if isinstance(var, IdentifierToken) else IdentifierToken(var) for var in bound_variables]

        def _create_lazy(name: str):
            return lambda scope: name

        for element in bound_variables:
            if isinstance(element, str):
                self.bound_variables.append(
                    (
                        StaticIdentifier(element.removeprefix("!")),
                        element.startswith("!"),
                    )
                )
            elif isinstance(element, tuple):
                token, is_static = element

                if isinstance(token, str):
                    self.bound_variables.append((StaticIdentifier(token), is_static))
                else:
                    self.bound_variables.append(element)
            else:
                raise ValueError(element)

        self.args = args
        self.body = body
        self.target = target
        self.prefix = prefix

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
                [arg.visit_parts(visitor) for arg in self.args],
                self.body.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target else None,
            ),
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.func_name == other.func_name
            and self.bound_variables == other.bound_variables
            and self.args == other.args
            and self.body == other.body
            and self.target == other.target
        )

    def __repr__(self):
        return f"DEF({self.prefix}{self.func_name}<{repr([('!:' if name[1] else '') + name[0](None) for name in self.bound_variables])[1:-1]}>({repr(self.args)[1:-1]}){'-> ' + repr(self.target) if self.target else ''} {{ {self.body} }})"

    def copy(self) -> "AbstractFunctionDefinitionAssembly":
        return type(self)(
            self.func_name,
            self.bound_variables.copy(),
            [arg.copy() for arg in self.args],
            self.body.copy(),
            target=self.target.copy() if self.target else None,
            prefix=self.prefix,
        )
