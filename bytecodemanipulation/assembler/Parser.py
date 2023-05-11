import typing
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import (
    IIdentifierAccessor,
    MacroExpandedIdentifier,
    StaticIdentifier,
)
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import _syntax_wrapper
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.expressions.AttributeAccessExpression import (
    AttributeAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.CallAssembly import (
    AbstractCallAssembly,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import (
    ConstantAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.DerefAccessExpression import (
    DerefAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.DiscardValueExpression import (
    DiscardValueExpression,
)
from bytecodemanipulation.data.shared.expressions.DynamicAccessExpression import (
    DynamicAttributeAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.GlobalAccessExpression import (
    GlobalAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.GlobalStaticAccessExpression import (
    GlobalStaticAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.LocalAccessExpression import (
    LocalAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.MacroAssembly import MacroAssembly
from bytecodemanipulation.data.shared.expressions.MacroParameterAcessExpression import (
    MacroParameterAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.ModuleAccessExpression import (
    ModuleAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.StaticAttributeAcccessExpression import (
    StaticAttributeAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.SubscriptionAccessExpression import (
    SubscriptionAccessExpression,
)
from bytecodemanipulation.data.shared.expressions.TopOfStackAccessExpression import (
    TopOfStackAccessExpression,
)
from bytecodemanipulation.data.shared.instructions.OpAssembly import AbstractOpAssembly

from bytecodemanipulation.MutableFunction import Instruction

from bytecodemanipulation.assembler.Lexer import (
    Lexer,
    SpecialToken,
    StringLiteralToken,
)

try:
    from code_parser.lexers.common import (
        AbstractToken,
        CommentToken,
        IdentifierToken,
        BinaryOperatorToken,
        IntegerToken,
        FloatToken,
        BracketToken,
    )
    from code_parser.parsers.common import (
        AbstractParser,
        AbstractExpression,
        NumericExpression,
        BracketExpression,
        BinaryExpression,
        IdentifierExpression,
    )
    import code_parser.parsers.common as parser_file

except ImportError:
    from bytecodemanipulation.assembler.util.tokenizer import (
        AbstractToken,
        CommentToken,
        IdentifierToken,
        BinaryOperatorToken,
        IntegerToken,
        FloatToken,
        BracketToken,
    )
    from bytecodemanipulation.assembler.util.parser import (
        AbstractParser,
        AbstractExpression,
        NumericExpression,
        BracketExpression,
        BinaryExpression,
        IdentifierExpression,
    )
    import bytecodemanipulation.assembler.util.parser as parser_file


def create_instruction(token: AbstractToken, *args, **kwargs) -> Instruction:
    instr = Instruction(*args, **kwargs)
    instr.source_location = token.line, token.column, token.span
    return instr


Instruction.create_with_token = create_instruction

parser_file.raise_syntax_error = _syntax_wrapper


class Parser(AbstractParser):
    INSTRUCTIONS: typing.Dict[str, typing.Type[AbstractAssemblyInstruction]] = {}

    T = typing.TypeVar(
        "T", typing.Type[AbstractAssemblyInstruction], AbstractAssemblyInstruction
    )

    @classmethod
    def register(cls, instr: T) -> T:
        cls.INSTRUCTIONS[instr.NAME] = instr
        return instr

    def __init__(
        self,
        tokens_or_str: str | typing.List[AbstractToken],
        scope: ParsingScope = None,
        initial_line_offset=0,
    ):
        super().__init__(
            tokens_or_str
            if isinstance(tokens_or_str, list)
            else Lexer(tokens_or_str, initial_line_offset=initial_line_offset).lex()
        )
        self.scope = scope or ParsingScope()

    def parse(self, scope: ParsingScope = None) -> CompoundExpression:
        """
        Starts parsing the text, and returns the CompoundExpression holding everything

        :param scope: the scope to use
        """
        self.scope = scope or self.scope
        return self.parse_while_predicate(
            lambda: not self.is_empty(), scope=scope or self.scope
        )

    def parse_body(
        self, namespace_part: str | list | None = None, scope: ParsingScope = None
    ) -> CompoundExpression:
        """
        Parses the body of an expression, containing a list of assembly instructions

        :param namespace_part: a suffix for the scope namespace
        :param scope: optional, the scope to use
        :return: the CompoundExpression representing the body
        :raises: SyntaxError: if EOF is reached before finalizing, or '}' was not found at the end to end the body
        """
        scope = scope or self.scope

        if namespace_part is not None:
            if isinstance(namespace_part, str):
                scope.scope_path.append(namespace_part)
            else:
                scope.scope_path += namespace_part

        if not self.try_consume(SpecialToken("{")):
            raise throw_positioned_syntax_error(
                scope, self.try_inspect(), "expected '{'"
            )

        body = self.parse_while_predicate(
            lambda: not self.try_consume(SpecialToken("}")),
            eof_error="Expected '}', got EOF",
            scope=scope,
        )

        if namespace_part:
            if isinstance(namespace_part, str):
                if self.scope.scope_path.pop(-1) != namespace_part:
                    raise RuntimeError
            else:
                if self.scope.scope_path[-len(namespace_part) :] != namespace_part:
                    raise RuntimeError

                del self.scope.scope_path[-len(namespace_part) :]

        return body

    def parse_while_predicate(
        self,
        predicate: typing.Callable[[], bool],
        eof_error: str = None,
        scope: ParsingScope = None,
    ) -> CompoundExpression:
        root = CompoundExpression()

        while predicate():
            if self.try_consume(CommentToken):
                continue

            if not (instr_token := self.try_consume(IdentifierToken)):
                raise throw_positioned_syntax_error(
                    scope, self.try_inspect(), "expected identifier"
                )

            if scope:
                scope.last_base_token = instr_token

            if instr_token.text not in self.INSTRUCTIONS:
                if not (instr := self.try_parse_custom_assembly(instr_token, scope)):
                    raise throw_positioned_syntax_error(
                        scope,
                        instr_token,
                        "expected <assembly instruction name> or <assembly macro name>",
                    )
            else:
                instr = self.INSTRUCTIONS[instr_token.text].consume(self, scope)

            root.add_child(instr)

            instr.fill_scope(self.scope)

            while self.try_consume(CommentToken):
                pass

            if self.is_empty():
                break

            if self.try_consume(SpecialToken(";")):
                continue

            if not (expr := self.try_inspect()):
                continue

            if self[-1].line != expr.line:
                continue

            if not predicate():
                if eof_error and self.try_inspect() is None:
                    print(self.try_inspect())
                    print(repr(root))
                    raise throw_positioned_syntax_error(scope, self[-1], eof_error)

                break

            print(self[-1].line, self[-1], expr.line)

            raise throw_positioned_syntax_error(
                scope,
                self.try_inspect(),
                "Expected <newline> or ';' after assembly instruction",
            )

        return root

    def try_parse_custom_assembly(
        self, base_token: IdentifierToken, scope: ParsingScope
    ):
        self.cursor -= 1
        self.save()
        self.cursor += 1

        name = [base_token.text]

        while self.try_consume(SpecialToken(":")):
            name.append(self.consume(IdentifierToken).text)

        target = self.scope.lookup_namespace(name, create=False, include_prefixes=True)

        if isinstance(target, MacroAssembly.MacroOverloadPage):
            for macro in typing.cast(
                MacroAssembly.MacroOverloadPage, target
            ).assemblies:
                if macro.allow_assembly_instr:
                    self.rollback()
                    # print(name)
                    return AbstractCallAssembly.IMPLEMENTATION.consume_macro_call(
                        self, scope
                    )

        self.rollback()

    def try_consume_access_to_value(
        self,
        allow_tos=True,
        allow_primitives=False,
        allow_op=True,
        allow_advanced_access=True,
        allow_calls=True,
        scope=None,
    ) -> AbstractAccessExpression | None:
        """
        Consumes an access to a value, for read or write access

        todo: add an option to force write compatibility
        todo: make it extendable

        :param allow_tos: if TOS (%) is allowed
        :param allow_primitives: if primitives are allowed, e.g. numeric literals
        :param allow_op: if operations are allowed, starting with OP
        :param allow_advanced_access: if expressions like @global[$index].attribute are allowed
        :param scope: the parsing scope instance
        :param allow_calls: if True, calls will be allowed as expressions
        """
        start_token = self.try_inspect()

        if start_token is None:
            return

        if allow_primitives:
            if string := self.try_consume(StringLiteralToken):
                return ConstantAccessExpression(string.text, string)

            if integer := self.try_consume(IntegerToken):
                return ConstantAccessExpression(
                    int(integer.text)
                    if "." not in integer.text
                    else float(integer.text),
                    integer,
                )

            if isinstance(start_token, IdentifierToken):
                if start_token.text == "None":
                    return ConstantAccessExpression(None, start_token)
                elif start_token.text == "True":
                    return ConstantAccessExpression(True, start_token)
                elif start_token.text == "False":
                    return ConstantAccessExpression(False, start_token)

        if not isinstance(start_token, (SpecialToken, IdentifierToken)):
            return

        if start_token.text == "@":
            self.consume(SpecialToken("@"), err_arg=scope)

            if self.try_consume(SpecialToken("!")):
                expr = GlobalStaticAccessExpression(
                    self.parse_identifier_like(scope), start_token
                )
            else:
                expr = GlobalAccessExpression(
                    self.parse_identifier_like(scope), start_token
                )

        elif start_token.text == "$":
            self.consume(SpecialToken("$"), err_arg=scope)
            expr = LocalAccessExpression(self.parse_identifier_like(scope), start_token)

        elif start_token.text == "§":
            self.consume(SpecialToken("§"), err_arg=scope)
            expr = DerefAccessExpression(self.parse_identifier_like(scope), start_token)

        elif start_token.text == "&":
            self.consume(SpecialToken("&"), err_arg=scope)
            expr = MacroParameterAccessExpression(
                self.parse_identifier_like(scope), start_token
            )

        elif start_token.text == "%" and allow_tos:
            self.consume(SpecialToken("%"), err_arg=scope)

            offset = self.try_consume(IntegerToken)

            if offset is not None:
                return TopOfStackAccessExpression(start_token, int(offset.text))

            expr = TopOfStackAccessExpression(start_token)

        elif start_token.text == "~":
            self.consume(SpecialToken("~"), err_arg=scope)
            expr = ModuleAccessExpression(
                self.parse_identifier_like(scope), start_token
            )

        elif start_token.text == "\\":
            self.consume(SpecialToken("\\"), err_arg=scope)
            expr = DiscardValueExpression()

        elif (
            start_token.text == "OP"
            and allow_op
            and "OP" in self.INSTRUCTIONS
            and AbstractOpAssembly.IMPLEMENTATION is not None
        ):
            self.consume(start_token, err_arg=scope)

            if not (opening := self.try_consume(SpecialToken("("))):
                raise throw_positioned_syntax_error(
                    scope,
                    self[-1:1],
                    "expected '(' after OP when used in expressions",
                )

            expr = AbstractOpAssembly.IMPLEMENTATION.consume(self, scope)

            if not self.try_consume(SpecialToken(")")):
                raise throw_positioned_syntax_error(
                    scope,
                    [opening, self[0]],
                    "expected ')' after operation",
                )

        else:
            return

        if allow_advanced_access:
            while True:
                if self.try_consume(SpecialToken("[")):
                    # Consume either an Integer or a expression
                    if not (
                        index := self.try_consume_access_to_value(
                            allow_primitives=True,
                            allow_tos=allow_tos,
                            allow_op=allow_op,
                            scope=scope,
                        )
                    ):
                        raise throw_positioned_syntax_error(
                            scope,
                            self.try_inspect() or self[-1],
                            "expected <expression>"
                            + (
                                ""
                                if not isinstance(self.try_inspect(), IdentifierToken)
                                else " (did you forget a prefix?)"
                            ),
                        )

                    if not self.try_consume(SpecialToken("]")):
                        raise throw_positioned_syntax_error(
                            scope, self.try_inspect() or self[-1], "expected ']''"
                        )

                    expr = SubscriptionAccessExpression(
                        expr,
                        index,
                    )

                elif self.try_consume(SpecialToken(".")):
                    if opening_bracket := self.try_consume(SpecialToken("(")):
                        if not (
                            index := self.try_consume_access_to_value(
                                allow_primitives=True,
                                allow_tos=allow_tos,
                                allow_op=allow_op,
                                scope=scope,
                                allow_calls=allow_calls,
                            )
                        ):
                            raise throw_positioned_syntax_error(
                                scope,
                                self.try_inspect() or self[-1],
                                "expected <expression>"
                                + (
                                    ""
                                    if not isinstance(
                                        self.try_inspect(), IdentifierToken
                                    )
                                    else " (did you forget a prefix?)"
                                ),
                            )

                        if not self.try_consume(SpecialToken(")")):
                            raise throw_positioned_syntax_error(
                                scope,
                                [opening_bracket, self.try_inspect()],
                                "expected ')'",
                            )

                        expr = DynamicAttributeAccessExpression(expr, index)

                    elif self.try_consume(SpecialToken("!")):
                        name = self.parse_identifier_like(scope)
                        expr = StaticAttributeAccessExpression(expr, name)

                    else:
                        name = self.parse_identifier_like(scope)
                        expr = AttributeAccessExpression(expr, name)

                elif self.try_inspect() == SpecialToken("(") and allow_calls:
                    expr = AbstractCallAssembly.IMPLEMENTATION.construct_from_partial(
                        expr, self, scope
                    )

                else:
                    break

        return expr

    def try_parse_data_source(
        self,
        allow_tos=True,
        allow_primitives=False,
        include_bracket=True,
        allow_op=True,
        allow_calls=True,
        scope=None,
    ) -> AbstractSourceExpression | None:
        self.save()

        if include_bracket and not self.try_consume(SpecialToken("(")):
            self.rollback()
            return

        if access := self.try_consume_access_to_value(
            allow_tos=allow_tos,
            allow_primitives=allow_primitives,
            allow_op=allow_op,
            allow_calls=allow_calls,
            scope=scope,
        ):
            self.discard_save()
            if include_bracket:
                self.consume(SpecialToken(")"))
            return access

        if allow_primitives:
            if string := self.try_consume(StringLiteralToken):
                return ConstantAccessExpression(string.text, string)

            if integer := self.try_consume(IntegerToken):
                return ConstantAccessExpression(int(integer.text), integer)

            if boolean := self.try_consume(
                (IdentifierToken("True"), IdentifierToken("False"))
            ):
                return ConstantAccessExpression(boolean.text == "True", boolean)

        # print("failed", self.try_inspect())

        self.rollback()

    def try_parse_identifier_like(self) -> IIdentifierAccessor | None:
        if expr := self.try_consume_multi([SpecialToken("&"), IdentifierToken]):
            return MacroExpandedIdentifier(expr[1].text, expr)

        if expr := self.try_consume(IdentifierToken):
            return StaticIdentifier(expr.text)

    def parse_identifier_like(self, scope: ParsingScope) -> IIdentifierAccessor:
        identifier = self.try_parse_identifier_like()

        if identifier is None:
            raise throw_positioned_syntax_error(
                scope,
                self[0],
                "expected <identifier> or &<identifier>",
            )

        return identifier
