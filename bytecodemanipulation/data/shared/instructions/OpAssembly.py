import typing
import abc
import typing
from collections import namedtuple

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction
from bytecodemanipulation.assembler.AbstractBase import ParsingScope


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


class AbstractOperator(abc.ABC):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        raise NotImplementedError


OperatorArgValue = namedtuple("OperatorArgValue", "index")


class OpcodeBaseOperator(AbstractOperator):
    def __init__(
        self,
        *opcodes: int
        | str
        | typing.Tuple[int | str, int]
        | typing.Tuple[
            int | str,
            typing.Callable[
                [MutableFunction, ParsingScope, typing.List[AbstractSourceExpression]],
                typing.Any,
            ],
        ]
        | OperatorArgValue,
    ):
        self.opcodes = opcodes

    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = []
        if not any(isinstance(param, OperatorArgValue) for param in self.opcodes):
            for param in parameters:
                bytecode += param.emit_bytecodes(function, scope)

        for opcode in self.opcodes:
            if isinstance(opcode, (int, str)):
                bytecode.append(Instruction(function, -1, opcode))
            elif isinstance(opcode, tuple):
                if isinstance(opcode[1], typing.Callable):
                    bytecode.append(
                        Instruction(
                            function,
                            -1,
                            opcode[0],
                            arg=opcode[1](function, scope, list(parameters)),
                        )
                    )
                else:
                    bytecode.append(Instruction(function, -1, opcode[0], arg=opcode[1]))
            elif isinstance(opcode, OperatorArgValue):
                bytecode += parameters[opcode.index].emit_bytecodes(function, scope)
            elif hasattr(opcode, "emit_bytecodes"):
                bytecode += opcode.emit_bytecodes(function, scope)
            else:
                raise ValueError(opcode)

        return bytecode


class AbstractOpAssembly(
    AbstractAssemblyInstruction, AbstractAccessExpression, abc.ABC
):
    """
    OP ... [-> <target>]
    - <expr> +|-|*|/|//|**|%|&|"|"|^|>>|<<|@|is|!is|in|!in|<|<=|==|!=|>|>=|xor|!xor|:=|isinstance|issubclass|hasattr|getattr <expr>
    - -|+|~|not|! <expr>
    """

    NAME = "OP"

    BINARY_OPS: typing.Dict[str, AbstractOperator] = {}
    SINGLE_OPS: typing.Dict[str, AbstractOperator] = {}
    PREFIX_OPERATORS: typing.Dict[
        str, typing.Tuple[AbstractOperator, int | None, bool | None, bool | None]
    ] = {}

    @classmethod
    def register_prefix_operator(
        cls,
        name: str,
        operator: AbstractOperator,
        arg_count: int = None,
        include_brackets: bool = None,
        has_coma_sep: bool = None,
    ):
        if arg_count is None:
            if include_brackets is False:
                raise ValueError(
                    "If 'include_brackets' is False, 'arg_count' must be set"
                )

            include_brackets = True

        cls.PREFIX_OPERATORS[name] = operator, arg_count, include_brackets, has_coma_sep

    class IOperation(IAssemblyStructureVisitable, abc.ABC):
        def copy(self):
            raise NotImplementedError

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            raise NotImplementedError

        def __eq__(self, other):
            raise NotImplementedError

        def __repr__(self):
            raise NotImplementedError

    class SingleOperation(IOperation):
        def __init__(
            self,
            operator: str,
            operator_token: typing.List[AbstractToken],
            expression: AbstractSourceExpression,
            base: typing.Type["AbstractOpAssembly"] = None,
        ):
            self.operator = operator
            self.operator_token = operator_token
            self.expression = expression
            self.base = base

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.operator == other.operator
                and self.expression == other.expression
            )

        def __repr__(self):
            return f"{self.operator} {self.expression}"

        def copy(self):
            return type(self)(
                self.operator, self.operator_token, self.expression.copy(), self.base
            )

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            try:
                return self.base.SINGLE_OPS[self.operator].emit_bytecodes(
                    function, scope, self.expression
                )
            except:
                raise throw_positioned_syntax_error(
                    scope,
                    self.operator_token,
                    "during emitting bytecode of singleton operator",
                )

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
            parents: list,
        ):
            return visitor(
                self,
                (
                    self.expression.visit_parts(visitor, parents + [self]),
                    parents,
                ),
            )

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

    class BinaryOperation(IOperation):
        def __init__(
            self,
            lhs: AbstractSourceExpression,
            operator: str,
            operator_token: typing.List[AbstractToken],
            rhs: AbstractSourceExpression,
            base: typing.Type["AbstractOpAssembly"] = None,
        ):
            self.base = base
            self.lhs = lhs
            self.operator = operator
            self.operator_token = operator_token
            self.rhs = rhs

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.lhs == other.lhs
                and self.operator == other.operator
                and self.rhs == other.rhs
            )

        def __repr__(self):
            return f"{self.lhs} {self.operator} {self.rhs}"

        def copy(self):
            return type(self)(
                self.lhs.copy(),
                self.operator,
                self.operator_token,
                self.rhs.copy(),
                self.base,
            )

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            try:
                return self.base.BINARY_OPS[self.operator].emit_bytecodes(
                    function, scope, self.lhs, self.rhs
                )
            except:
                raise throw_positioned_syntax_error(
                    scope,
                    self.operator_token,
                    "during emitting bytecode of binary operation",
                )

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
            parents: list,
        ):
            return visitor(
                self,
                (
                    self.lhs.visit_parts(visitor, parents + [self]),
                    self.rhs.visit_parts(visitor, parents + [self]),
                ),
                parents,
            )

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

    class PrefixOperator(IOperation):
        def __init__(
            self,
            operator: str,
            operator_token: typing.List[AbstractToken],
            args: typing.List[AbstractSourceExpression],
            base: typing.Type["AbstractOpAssembly"] = None,
        ):
            self.base = base
            self.operator = operator
            self.operator_token = operator_token
            self.args = args

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.args == other.args
                and self.operator == other.operator
            )

        def __repr__(self):
            return f"{self.operator} {repr(self.args)[1:-1]}"

        def copy(self):
            return type(self)(
                self.operator, self.operator_token, [arg.copy() for arg in self.args]
            )

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            try:
                return self.base.PREFIX_OPERATORS[self.operator][0].emit_bytecodes(
                    function, scope, *self.args
                )
            except:
                raise throw_positioned_syntax_error(
                    scope,
                    self.operator_token,
                    "during emitting bytecode of binary operation",
                )

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
            parents: list,
        ):
            return visitor(
                self,
                tuple(
                    [arg.visit_parts(visitor, parents + [self]) for arg in self.args]
                ),
                parents,
            )

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

    MAX_TOKENS_FOR_OPERATORS = 3

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "AbstractOpAssembly":
        if expr := cls.try_consume_binary(parser, scope):
            return cls(expr, cls.try_consume_arrow(parser, scope))

        if expr := cls.try_consume_single(parser, scope):
            return cls(expr, cls.try_consume_arrow(parser, scope))

        if expr := cls.try_consume_prefix(parser, scope):
            return cls(expr, cls.try_consume_arrow(parser, scope))

        raise throw_positioned_syntax_error(
            scope,
            parser.try_inspect(),
            "expected <operator> or <expression> <operator> ...",
        )

    @classmethod
    def try_consume_operator_name(
        cls, parser: "Parser", scope: ParsingScope, source: typing.Dict[str, typing.Any]
    ) -> typing.List[AbstractToken] | None:
        for count in range(cls.MAX_TOKENS_FOR_OPERATORS - 1, 0, -1):
            operator = parser[0:count]

            if operator and "".join(map(lambda e: e.text, operator)) in source:
                if not parser.try_consume_multi(operator):
                    raise RuntimeError

                return operator

    @classmethod
    def try_consume_arrow(
        cls, parser: "Parser", scope: ParsingScope
    ) -> AbstractAccessExpression | None:
        if parser.try_consume(SpecialToken("-")):
            if not parser.try_consume(SpecialToken(">")):
                raise throw_positioned_syntax_error(
                    scope,
                    parser[-1:1] + [scope.last_base_token],
                    "expected '>' after '-' to complete '->'",
                )

            return parser.try_consume_access_to_value(scope=scope)

    @classmethod
    def try_consume_single(
        cls, parser: "Parser", scope: ParsingScope
    ) -> typing.Optional[IOperation]:
        operator_tokens = cls.try_consume_operator_name(parser, scope, cls.SINGLE_OPS)

        if operator_tokens is None:
            return

        expression = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False
        )

        if expression is None:
            parser.rollback()
            return

        return cls.SingleOperation(
            "".join(map(lambda e: e.text, operator_tokens)),
            operator_tokens,
            expression,
            base=cls,
        )

    @classmethod
    def try_consume_binary(
        cls, parser: "Parser", scope: ParsingScope
    ) -> typing.Optional[IOperation]:
        parser.save()

        lhs = parser.try_parse_data_source(allow_primitives=True, include_bracket=False)

        if lhs is None:
            parser.rollback()
            return

        operator_tokens = cls.try_consume_operator_name(parser, scope, cls.BINARY_OPS)

        if operator_tokens is None:
            parser.rollback()
            return

        rhs = parser.try_parse_data_source(allow_primitives=True, include_bracket=False)

        if rhs is None:
            print("rhs is invalid")
            parser.rollback()
            return

        parser.discard_save()

        return cls.BinaryOperation(
            lhs,
            "".join(map(lambda e: e.text, operator_tokens)),
            operator_tokens,
            rhs,
            base=cls,
        )

    @classmethod
    def try_consume_prefix(
        cls, parser: "Parser", scope: ParsingScope
    ) -> typing.Optional[IOperation]:
        operator_tokens = cls.try_consume_operator_name(
            parser, scope, cls.PREFIX_OPERATORS
        )
        operator = "".join(map(lambda e: e.text, operator_tokens))
        operator_def, arg_count, has_brackets, has_coma_sep = cls.PREFIX_OPERATORS[
            operator
        ]

        bracket = parser.try_consume(SpecialToken("("))

        if bracket is None and has_brackets is True:
            raise throw_positioned_syntax_error(scope, parser[0], "expected '('")
        elif bracket is not None and has_brackets is False:
            raise throw_positioned_syntax_error(
                scope,
                operator_tokens + [parser[0]],
                "did not expect '(' after operator name",
            )

        args = []

        if arg_count is not None:
            for _ in range(arg_count):
                expr = parser.try_consume_access_to_value(
                    scope=scope,
                    allow_calls=True,
                    allow_tos=True,
                    allow_primitives=True,
                    allow_op=True,
                    allow_advanced_access=True,
                )

                if expr is None:
                    raise throw_positioned_syntax_error(
                        scope, parser[0], "expected <expression>"
                    )

                args.append(expr)

                coma = parser.try_consume(SpecialToken(","))

                if coma is None and has_coma_sep is True:
                    raise throw_positioned_syntax_error(
                        scope, parser[0], "expected ','"
                    )

                elif coma is not None and has_coma_sep is False:
                    raise throw_positioned_syntax_error(
                        scope, coma, "did not expect ',' for separation of args"
                    )
        else:
            while not parser.try_inspect() == SpecialToken(")"):
                expr = parser.try_consume_access_to_value(
                    scope=scope,
                    allow_calls=True,
                    allow_tos=True,
                    allow_primitives=True,
                    allow_op=True,
                    allow_advanced_access=True,
                )

                if expr is None:
                    raise throw_positioned_syntax_error(
                        scope, parser[0], "expected <expression>"
                    )

                args.append(expr)

                coma = parser.try_consume(SpecialToken(","))

                if (
                    coma is None
                    and has_coma_sep is True
                    and parser[0] != SpecialToken(")")
                ):
                    raise throw_positioned_syntax_error(
                        scope, parser[0], "expected ','"
                    )

                elif coma is not None and has_coma_sep is False:
                    raise throw_positioned_syntax_error(
                        scope, coma, "did not expect ',' for separation of args"
                    )

        if bracket and not parser.try_consume(SpecialToken(")")):
            raise throw_positioned_syntax_error(scope, parser[0], "expected ')'")

        return cls.PrefixOperator(operator, operator_tokens, args, base=cls)

    def __init__(
        self, operation: IOperation, target: AbstractAccessExpression | None = None
    ):
        if operation is None:
            raise ValueError("operation cannot be null!")

        self.operation = operation
        self.target = target

    def copy(self) -> "AbstractOpAssembly":
        return type(self)(
            self.operation.copy(), self.target.copy() if self.target else None
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.operation == other.operation
            and self.target == other.target
        )

    def __repr__(self):
        return f"OP({self.operation}{', ' + repr(self.target) if self.target else ''})"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.operation.emit_bytecodes(function, scope) + (
            []
            if self.target is None
            else self.target.emit_store_bytecodes(function, scope)
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError(f"cannot assign to an '{self.operation}' operator!")

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
                self.operation.visit_parts(visitor, parents + [self]),
                self.target.visit_parts(
                    visitor,
                    parents + [self],
                )
                if self.target
                else None,
            ),
            parents,
        )
