import abc
import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import AbstractAssemblyInstruction
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class OpAssembly(AbstractAssemblyInstruction, AbstractAccessExpression):
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
    ] = {
        "+": Opcodes.BINARY_ADD,
        "-": Opcodes.BINARY_SUBTRACT,
        "*": Opcodes.BINARY_MULTIPLY,
        "/": Opcodes.BINARY_TRUE_DIVIDE,
        "//": Opcodes.BINARY_FLOOR_DIVIDE,
        "**": Opcodes.BINARY_MULTIPLY,
        "%": Opcodes.BINARY_MODULO,
        "&": Opcodes.BINARY_AND,
        "|": Opcodes.BINARY_OR,
        "^": Opcodes.BINARY_XOR,
        ">>": Opcodes.BINARY_RSHIFT,
        "<<": Opcodes.BINARY_LSHIFT,
        "@": Opcodes.BINARY_MATRIX_MULTIPLY,
        "is": (Opcodes.IS_OP, 0),
        "!is": (Opcodes.IS_OP, 1),
        "in": (Opcodes.CONTAINS_OP, 0),
        "!in": (Opcodes.CONTAINS_OP, 1),
        "<": (Opcodes.COMPARE_OP, 0),
        "<=": (Opcodes.COMPARE_OP, 1),
        "==": (Opcodes.COMPARE_OP, 2),
        "!=": (Opcodes.COMPARE_OP, 3),
        ">": (Opcodes.COMPARE_OP, 4),
        ">=": (Opcodes.COMPARE_OP, 5),
        # todo: is there a better way?
        "xor": (Opcodes.COMPARE_OP, 3),
        "!xor": (Opcodes.COMPARE_OP, 2),
        ":=": lambda lhs, rhs, function, scope: rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.DUP_TOP)]
        + lhs.emit_store_bytecodes(function, scope),
        "isinstance": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, isinstance)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
        "issubclass": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, issubclass)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
        "hasattr": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, hasattr)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
        "getattr": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, getattr)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
    }

    # todo: parse and implement
    SINGLE_OPS: typing.Dict[
        str,
        typing.Tuple[int, int]
        | int
        | typing.Callable[
            [AbstractAccessExpression, MutableFunction, ParsingScope],
            Instruction | typing.List[Instruction],
        ],
    ] = {
        "-": Opcodes.UNARY_NEGATIVE,
        "+": Opcodes.UNARY_POSITIVE,
        "~": Opcodes.UNARY_INVERT,
        "not": Opcodes.UNARY_NOT,
        "!": Opcodes.UNARY_NOT,
    }

    # todo: and, or, nand, nor, inplace variants

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
        ):
            self.operator = operator
            self.expression = expression

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
            opcode_info = OpAssembly.SINGLE_OPS[self.operator]

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
        ):
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
            opcode_info = OpAssembly.BINARY_OPS[self.operator]

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

            return cls.SingleOperation(expr.text, expression)

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

        return OpAssembly.BinaryOperation(lhs, OP_NAME, rhs)

    def __init__(
        self, operation: IOperation, target: AbstractAccessExpression | None = None
    ):
        if operation is None:
            raise ValueError("operation cannot be null!")

        self.operation = operation
        self.target = target

    def copy(self) -> "OpAssembly":
        return OpAssembly(
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
