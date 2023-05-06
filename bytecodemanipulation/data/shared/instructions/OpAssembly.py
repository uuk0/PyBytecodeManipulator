import typing
import abc
import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.MutableFunction import Instruction


class AbstractOpAssembly(AbstractAssemblyInstruction, AbstractAccessExpression, abc.ABC):
    """
    OP ... [-> <target>]
    - <expr> +|-|*|/|//|**|%|&|"|"|^|>>|<<|@|is|!is|in|!in|<|<=|==|!=|>|>=|xor|!xor|:=|isinstance|issubclass|hasattr|getattr <expr>
    - -|+|~|not|! <expr>
    """

    NAME = "OP"

    BINARY_OPS: typing.Dict[
        str,
        typing.Tuple[int, int]
        | int
        | typing.Callable[
            [
                AbstractAccessExpression,
                AbstractAccessExpression,
                MutableFunction,
                ParsingScope,
            ],
            Instruction | typing.List[Instruction],
        ],
    ] = {}

    SINGLE_OPS: typing.Dict[
        str,
        typing.Tuple[int, int]
        | int
        | typing.Callable[
            [AbstractAccessExpression, MutableFunction, ParsingScope],
            Instruction | typing.List[Instruction],
        ],
    ] = {}

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
            expression: AbstractAccessExpression,
            base: typing.Type["AbstractOpAssembly"] = None,
        ):
            self.operator = operator
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
            return type(self)(self.operator, self.expression.copy())

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            opcode_info = self.base.SINGLE_OPS[self.operator]

            if callable(opcode_info):
                result = opcode_info(self.expression, function, scope)

                if isinstance(result, Instruction):
                    return self.expression.emit_bytecodes(function, scope) + [result]

                return result

            if isinstance(opcode_info, int):
                opcode, arg = opcode_info, 0
            else:
                opcode, arg = opcode_info

            return self.expression.emit_bytecodes(function, scope) + [
                Instruction(function, -1, opcode, arg=arg)
            ]

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
            lhs: AbstractAccessExpression,
            operator: str,
            rhs: AbstractAccessExpression,
            base: typing.Type["AbstractOpAssembly"] = None,
        ):
            self.base = base
            self.lhs = lhs
            self.operator = operator
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
            return type(self)(self.lhs.copy(), self.operator, self.rhs.copy())

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            opcode_info = self.base.BINARY_OPS[self.operator]

            if callable(opcode_info):
                result = opcode_info(self.lhs, self.rhs, function, scope)

                if isinstance(result, Instruction):
                    return (
                        self.lhs.emit_bytecodes(function, scope)
                        + self.rhs.emit_bytecodes(function, scope)
                        + [result]
                    )

                return result

            if isinstance(opcode_info, int):
                opcode, arg = opcode_info, 0
            else:
                opcode, arg = opcode_info

            return (
                self.lhs.emit_bytecodes(function, scope)
                + self.rhs.emit_bytecodes(function, scope)
                + [Instruction(function, -1, opcode, arg=arg)]
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

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "OpAssembly":
        if expr := cls.try_consume_single(parser):
            return cls(expr, cls.try_consume_arrow(parser, scope))

        if expr := cls.try_consume_binary(parser):
            return cls(expr, cls.try_consume_arrow(parser, scope))

        raise throw_positioned_syntax_error(
            scope,
            parser.try_inspect(),
            "expected <operator> or <expression> <operator> ...",
        )

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
    def try_consume_single(cls, parser: "Parser") -> typing.Optional[IOperation]:
        parser.save()
        if not (expr := parser.try_consume(IdentifierToken)):
            parser.rollback()
            return

        if expr.text in cls.SINGLE_OPS:
            expression = parser.try_parse_data_source(
                allow_primitives=True, include_bracket=False
            )

            if expression is None:
                parser.rollback()

            return cls.SingleOperation(expr.text, expression, base=cls)

    @classmethod
    def try_consume_binary(cls, parser: "Parser") -> typing.Optional[IOperation]:
        parser.save()

        lhs = parser.try_parse_data_source(allow_primitives=True, include_bracket=False)

        if lhs is None:
            parser.rollback()
            return

        part = parser[0:2]

        if part:
            first, second = part
        else:
            first, second = parser[0], None

        if first and second and (first.text + second.text) in cls.BINARY_OPS:
            OP_NAME = first.text + second.text
            parser.consume(first)
            parser.consume(second)

        elif first and first.text in cls.BINARY_OPS:
            OP_NAME = first.text
            parser.consume(first)

        else:
            raise SyntaxError(f"No valid operator found: {first}, {second}")

        rhs = parser.try_parse_data_source(allow_primitives=True, include_bracket=False)

        if rhs is None:
            print("rhs is None")
            parser.rollback()
            return

        parser.discard_save()

        return AbstractOpAssembly.BinaryOperation(lhs, OP_NAME, rhs, base=cls)

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
