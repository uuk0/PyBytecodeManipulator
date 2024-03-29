import abc
import typing

from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import IIdentifierAccessor
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.AbstractBase import StaticIdentifier
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import (
    PropagatingCompilerException,
    TraceInfo,
)
from bytecodemanipulation.assembler.util.parser import AbstractExpression
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
        prefix = cls._parse_name_prefix(parser, scope)

        func_name = parser.parse_identifier_like(scope)

        bound_variables = cls._parse_bound_variables(parser, scope)
        args = cls._parse_arg_list(parser, bound_variables, scope)

        if expr := parser.try_consume(SpecialToken("<")):
            if bound_variables:
                raise PropagatingCompilerException(
                    "got '<' after '('... ')' expression, where a '{'... '}' (code block) was expected"
                ).add_trace_level(scope.get_trace_info().with_token(expr))

            raise PropagatingCompilerException(
                "Respect ordering (got '<' before 'args'): DEF ['name'] ['captured'] ('args') [-> 'target'] { 'code' }"
            ).add_trace_level(scope.get_trace_info().with_token(expr))

        target = parser.try_parse_target_expression(scope)

        try:
            body = parser.parse_body(scope=scope)
        except PropagatingCompilerException as e:
            e.add_trace_level(
                scope.get_trace_info().with_token(list(func_name.get_tokens())),
                message=f"during parsing function definition {func_name(scope)}",
            )
            raise e

        if expr := parser.try_consume(SpecialToken("-")):
            raise PropagatingCompilerException(
                "Respect ordering (got '-' before 'args'): DEF ['name'] ['captured'] ('args') [-> 'target'] { 'code' }"
            ).add_trace_level(scope.get_trace_info().with_token(expr))

        return cls(
            func_name,
            bound_variables,
            args,
            body,
            target,
            prefix=prefix,
            trace_info=scope.get_trace_info().with_token(list(func_name.get_tokens())),
        )

    @classmethod
    def _parse_arg_list(cls, parser: Parser, bound_variables, scope):
        args = []

        if (opening_bracket := parser.try_consume(SpecialToken("("))) is None:
            raise PropagatingCompilerException(
                f"expected '(' after <{'bound variables' if bound_variables else 'identifier'}>"
            ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        while parser.try_inspect() != SpecialToken(")"):
            arg = cls._pare_argument(parser, scope)

            if arg is None:
                break

            args.append(arg)

            if not parser.try_consume(SpecialToken(",")):
                break

        if not parser.try_consume(SpecialToken(")")):
            raise PropagatingCompilerException(
                "expected ')' matching '(' in function definition"
            ).add_trace_level(
                scope.get_trace_info().with_token(opening_bracket, parser[0])
            )

        return args

    @classmethod
    def _pare_argument(
        cls, parser: Parser, scope: ParsingScope
    ) -> AbstractCallAssembly.IArg | None:
        arg = None

        star = parser.try_consume(SpecialToken("*"))
        star_star = parser.try_consume(SpecialToken("*"))
        identifier = parser.try_parse_identifier_like()

        if not identifier:
            if star:
                raise PropagatingCompilerException(
                    "Expected <identifier> after '**'"
                    if star_star
                    else "Expected <identifier> after '*'"
                ).add_trace_level(scope.get_trace_info().with_token(star, star_star))
            return

        if not star:
            if equal_sign := parser.try_consume(SpecialToken("=")):
                default_value = parser.try_consume_access_to_value(
                    allow_primitives=True,
                    allow_op=True,
                    scope=scope,
                )

                if default_value is None:
                    raise PropagatingCompilerException(
                        "expected <expression> after '='"
                    ).add_trace_level(
                        scope.get_trace_info().with_token(
                            list(identifier.get_tokens()), equal_sign, parser[0]
                        )
                    )

                arg = AbstractCallAssembly.KwArg(
                    identifier, default_value, token=identifier
                )

        if not arg:
            if star_star:
                arg = AbstractCallAssembly.KwArgStar(identifier, token=identifier)

            elif star:
                arg = AbstractCallAssembly.StarArg(identifier, token=identifier)

            else:
                arg = AbstractCallAssembly.Arg(identifier, token=identifier)

        return arg

    @classmethod
    def _parse_bound_variables(cls, parser, scope):
        bound_variables: typing.List[typing.Tuple[IIdentifierAccessor, bool]] = []
        if parser.try_consume(SpecialToken("<")):
            is_static = bool(parser.try_consume(SpecialToken("!")))

            if expr := parser.try_parse_identifier_like():
                bound_variables.append((expr, is_static))

                while parser.try_consume(SpecialToken(",")) and (
                    expr := parser.try_parse_identifier_like()
                ):
                    bound_variables.append((expr, is_static))

            parser.consume(SpecialToken(">"), err_arg=scope)
        return bound_variables

    @classmethod
    def _parse_name_prefix(cls, parser, scope):
        prefix = ""
        while parser.try_consume(SpecialToken("|")):
            prefix += "|"
        if prefix == "":
            while parser.try_consume(SpecialToken(":")):
                prefix += ":"

        elif error := parser.try_consume(SpecialToken(":")):
            raise PropagatingCompilerException(
                "Cannot parser '|' and ':' as inter-fix for <function name>",
            ).add_trace_level(
                scope.get_trace_info().with_token(scope.last_base_token, error)
            )
        return prefix

    def __init__(
        self,
        func_name: IIdentifierAccessor | str | None,
        bound_variables: typing.List[typing.Tuple[IIdentifierAccessor, bool] | str],
        args: typing.List[AbstractCallAssembly.IArg],
        body: CompoundExpression,
        target: AbstractAccessExpression | None = None,
        prefix="",
        trace_info: TraceInfo = None,
    ):
        self.func_name = (
            StaticIdentifier(func_name) if isinstance(func_name, str) else func_name
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
        self.trace_info = trace_info

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
        return f"DEF({self.prefix}{self.func_name}<{repr([('!:' if name[1] else '') + name[0](None) for name in self.bound_variables])[1:-1]}>({repr(self.args)[1:-1]}){f'-> {repr(self.target)}' if self.target else ''} {{ {self.body} }})"

    def copy(self) -> "AbstractFunctionDefinitionAssembly":
        return type(self)(
            self.func_name,
            self.bound_variables.copy(),
            [arg.copy() for arg in self.args],
            self.body.copy(),
            target=self.target.copy() if self.target else None,
            prefix=self.prefix,
        )
