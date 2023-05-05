import abc
import functools
import itertools
import typing

import bytecodemanipulation.util
from bytecodemanipulation.Opcodes import Opcodes

from bytecodemanipulation.assembler.Parser import (
    Parser,
    AbstractAssemblyInstruction,
    AbstractAccessExpression,
    AbstractSourceExpression,
    ConstantAccessExpression,
    GlobalAccessExpression,
    LocalAccessExpression,
    CompoundExpression,
    AbstractExpression,
    IAssemblyStructureVisitable,
    JumpToLabel,
    ParsingScope,
    MacroAccessExpression,
    MacroAssembly,
    throw_positioned_syntax_error,
    AbstractCallAssembly,
)
from bytecodemanipulation.assembler.Lexer import (
    SpecialToken,
    IdentifierToken,
    IntegerToken,
    AbstractToken,
)
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction
from bytecodemanipulation.util import LambdaInstructionWalker


@Parser.register
class RaiseAssembly(AbstractAssemblyInstruction):
    # RAISE [<source>]
    NAME = "RAISE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "RaiseAssembly":
        return cls(parser.try_parse_data_source(include_bracket=False))

    def __init__(self, source: AbstractSourceExpression = None):
        self.source = source

    def __eq__(self, other):
        return type(self) == type(other) and self.source == other.source

    def __repr__(self):
        return f"RAISE({'TOS' if self.source is None else self.source})"

    def copy(self):
        return type(self)(self.source.copy() if self.source else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + [Instruction(function, -1, Opcodes.RAISE_VARARGS, arg=1)]


@Parser.register
class LoadAssembly(AbstractAssemblyInstruction):
    # LOAD <access> [-> <target>]
    NAME = "LOAD"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "LoadAssembly":
        access_expr = parser.try_consume_access_to_value(
            allow_tos=False, allow_primitives=True, scope=scope
        )

        if access_expr is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        if parser.try_consume(SpecialToken("-")):
            if not parser.try_consume(SpecialToken(">")):
                raise throw_positioned_syntax_error(
                    scope,
                    parser[-1:1] + [scope.last_base_token],
                    "expected '>' after '-' to complete '->'",
                )

            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(access_expr, target)

    def __init__(
        self,
        access_expr: AbstractAccessExpression,
        target: AbstractAccessExpression | None = None,
    ):
        self.access_expr = access_expr
        self.target = target

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.access_expr == other.access_expr
            and self.target == other.target
        )

    def __repr__(self):
        return (
            f"LOAD({self.access_expr}{', ' + repr(self.target) if self.target else ''})"
        )

    def copy(self) -> "LoadAssembly":
        return LoadAssembly(self.access_expr, self.target)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.access_expr.emit_bytecodes(function, scope) + (
            self.target.emit_store_bytecodes(function, scope) if self.target else []
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
            self,
            (
                self.access_expr.visit_parts(visitor, parents + [self]),
                self.target.visit_parts(visitor, parents + [self])
                if self.target is not None
                else None,
            ),
            parents,
        )


@Parser.register
class StoreAssembly(AbstractAssemblyInstruction):
    # STORE <access> [(expression)]
    NAME = "STORE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "StoreAssembly":
        access = parser.try_consume_access_to_value(allow_tos=False, scope=scope, allow_calls=False)

        if access is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        source = parser.try_parse_data_source()

        return cls(access, source)

    def __init__(
        self,
        access_token: AbstractAccessExpression,
        source: AbstractSourceExpression | None = None,
    ):
        self.access_token = access_token
        self.source = source

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.access_token == other.access_token
            and self.source == other.source
        )

    def __repr__(self):
        return f"STORE({self.access_token}, {self.source})"

    def copy(self) -> "StoreAssembly":
        return StoreAssembly(
            self.access_token, self.source.copy() if self.source else None
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + self.access_token.emit_store_bytecodes(function, scope)

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
                self.access_token.visit_parts(visitor, parents + [self]),
                self.source.visit_parts(visitor, parents + [self])
                if self.source is not None
                else None,
            ),
            parents,
        )


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


@Parser.register
class IFAssembly(AbstractAssemblyInstruction):
    # IF <expression> ['\'' <label name> '\''] '{' <body> '}'
    NAME = "IF"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "IFAssembly":
        source = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False, scope=scope
        )

        if source is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        if parser.try_consume(SpecialToken("'")):
            label_name = parser.consume(IdentifierToken)
            if not parser.try_consume(SpecialToken("'")):
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected '"
                )
        else:
            label_name = None

        body = parser.parse_body(scope=scope)

        return cls(
            source,
            body,
            label_name,
        )

    def __init__(
        self,
        source: AbstractSourceExpression,
        body: CompoundExpression,
        label_name: IdentifierToken | str | None = None,
    ):
        self.source = source
        self.body = body
        self.label_name = (
            label_name
            if not isinstance(label_name, str)
            else IdentifierToken(label_name)
        )

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy(), self.label_name)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.body == other.body
            and self.label_name == other.label_name
        )

    def __repr__(self):
        c = "'"
        return f"IF({self.source}{'' if self.label_name is None else ', label='+c+self.label_name.text+c}) -> {{{self.body}}}"

    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):

        if self.label_name is None:
            end = Instruction(function, -1, "NOP")
        else:
            end = Instruction(
                function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text + "_END"
            )

        return (
            (
                []
                if self.label_name is None
                else [
                    Instruction(
                        function,
                        -1,
                        Opcodes.BYTECODE_LABEL,
                        self.label_name.text + "_HEAD",
                    )
                ]
            )
            + self.source.emit_bytecodes(function, scope)
            + [Instruction(function, -1, "POP_JUMP_IF_FALSE", end)]
            + (
                []
                if self.label_name is None
                else [
                    Instruction(
                        function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text
                    )
                ]
            )
            + self.body.emit_bytecodes(function, scope)
            + [end]
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
            self, (self.source.visit_parts(visitor), self.body.visit_parts(visitor))
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))

    def get_labels(self) -> typing.Set[str]:
        return (
            set()
            if self.label_name is None
            else {
                self.label_name.text,
                self.label_name.text + "_END",
                self.label_name.text + "_HEAD",
            }
        ) | self.body.get_labels()


@Parser.register
class WHILEAssembly(AbstractAssemblyInstruction):
    # WHILE <expression> ['\'' <label name> '\''] '{' <body> '}'
    NAME = "WHILE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "WHILEAssembly":
        condition = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False, scope=scope
        )

        if condition is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        if parser.try_consume(SpecialToken("'")):
            label_name = parser.consume(IdentifierToken)
            if not parser.try_consume(SpecialToken("'")):
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected '"
                )
        else:
            label_name = None

        body = parser.parse_body(scope=scope)

        return cls(
            condition,
            body,
            label_name,
        )

    def __init__(
        self,
        source: AbstractSourceExpression,
        body: CompoundExpression,
        label_name: IdentifierToken | str | None = None,
    ):
        self.source = source
        self.body = body
        self.label_name = (
            label_name
            if not isinstance(label_name, str)
            else IdentifierToken(label_name)
        )

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy(), self.label_name)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.body == other.body
            and self.label_name == other.label_name
        )

    def __repr__(self):
        c = "'"
        return f"WHILE({self.source}{'' if self.label_name is None else ', label='+c+self.label_name.text+c}) -> {{{self.body}}}"

    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):
        if self.label_name is None:
            end = Instruction(function, -1, "NOP")
        else:
            end = Instruction(
                function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text + "_END"
            )

        CONDITION = self.source.emit_bytecodes(function, scope)

        if self.label_name:
            CONDITION.insert(
                0,
                Instruction(function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text),
            )

        HEAD = Instruction(function, -1, "POP_JUMP_IF_FALSE", end)

        BODY = self.body.emit_bytecodes(function, scope)

        if self.label_name:
            BODY.insert(
                0,
                Instruction(
                    function,
                    -1,
                    Opcodes.BYTECODE_LABEL,
                    self.label_name.text + "_INNER",
                ),
            )

        JUMP_BACK = Instruction(function, -1, "JUMP_ABSOLUTE", CONDITION[0])

        return CONDITION + [HEAD] + BODY + [JUMP_BACK, end]

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.source.visit_parts(visitor), self.body.visit_parts(visitor))
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))

    def get_labels(self):
        return (
            set()
            if self.label_name is None
            else {
                self.label_name.text,
                self.label_name.text + "_END",
                self.label_name.text + "_INNER",
            }
        ) | self.body.get_labels()


@Parser.register
class LoadGlobalAssembly(AbstractAssemblyInstruction):
    # LOAD_GLOBAL <name> [-> <target>]
    NAME = "LOAD_GLOBAL"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "LoadGlobalAssembly":
        parser.try_consume(SpecialToken("@"))

        name = parser.try_consume([IdentifierToken, IntegerToken])

        if name is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <name> or <integer>"
            )

        if parser.try_consume(SpecialToken("-")):
            if not parser.try_consume(SpecialToken(">")):
                raise throw_positioned_syntax_error(
                    scope,
                    parser[-1:1] + [scope.last_base_token],
                    "expected '>' after '-'",
                )

            target = parser.try_consume_access_to_value(scope=scope)

            if target is None:
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected <expression>"
                )
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

    def copy(self) -> "LoadGlobalAssembly":
        return LoadGlobalAssembly(self.name_token, self.target)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_GLOBAL", value)] + (
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


@Parser.register
class StoreGlobalAssembly(AbstractAssemblyInstruction):
    # STORE_GLOBAL <name> [<source>]
    NAME = "STORE_GLOBAL"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "StoreGlobalAssembly":
        parser.try_consume(SpecialToken("@"))
        name = parser.try_consume([IdentifierToken, IntegerToken])

        if name is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <name> or <integer>"
            )

        source = parser.try_parse_data_source()

        return cls(name, source)

    def __init__(
        self,
        name_token: IdentifierToken | IntegerToken | str | int,
        source: AbstractSourceExpression | None = None,
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
        self.source = source

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name_token == other.name_token
            and self.source == other.source
        )

    def __repr__(self):
        return f"STORE_GLOBAL({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "StoreGlobalAssembly":
        return StoreGlobalAssembly(
            self.name, self.source.copy() if self.source else None
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + [Instruction(function, -1, "STORE_GLOBAL", value)]

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.source.visit_parts(visitor) if self.target else None,)
        )


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


@Parser.register
class StoreFastAssembly(AbstractAssemblyInstruction):
    # STORE_FAST <name> [<source>]
    NAME = "STORE_FAST"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "StoreFastAssembly":
        parser.try_consume(SpecialToken("$"))
        name = parser.consume([IdentifierToken, IntegerToken])

        source = parser.try_parse_data_source()

        return cls(name, source)

    def __init__(
        self,
        name_token: IdentifierToken | IntegerToken | str | int,
        source: AbstractSourceExpression | None = None,
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
        self.source = source

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name_token == other.name_token
            and self.source == other.source
        )

    def __repr__(self):
        return f"STORE_FAST({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "StoreFastAssembly":
        return StoreFastAssembly(self.name, self.source.copy() if self.source else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return (
            [] if self.source is None else self.source.emit_bytecodes(function, scope)
        ) + [Instruction(function, -1, "STORE_FAST", value)]

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(
            self, (self.source.visit_parts(visitor) if self.target else None,)
        )


@Parser.register
class LoadConstAssembly(AbstractAssemblyInstruction):
    # LOAD_CONST <expression> | @<global const source> [-> <target>]
    NAME = "LOAD_CONST"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "LoadConstAssembly":
        value = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False
        )

        if not isinstance(value, (ConstantAccessExpression, GlobalAccessExpression)):
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <constant epxression>"
            )

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(value, target)

    def __init__(
        self,
        value: ConstantAccessExpression | GlobalAccessExpression | typing.Any,
        target: AbstractAccessExpression | None = None,
    ):
        self.value = (
            value
            if isinstance(value, (ConstantAccessExpression, GlobalAccessExpression))
            else ConstantAccessExpression(value)
        )
        self.target = target

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.value == other.value
            and self.target == other.target
        )

    def __repr__(self):
        return f"LOAD_CONST({self.value.value if not isinstance(self.value, GlobalAccessExpression) else self.target}{', ' + repr(self.target) if self.target else ''})"

    def copy(self) -> "LoadConstAssembly":
        return LoadConstAssembly(self.value, self.target)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [
            Instruction(
                function,
                -1,
                "LOAD_CONST",
                self.value.value
                if isinstance(self.value, ConstantAccessExpression)
                else function.target.__globals__.get(self.value.name_token.text),
            )
        ] + (self.target.emit_bytecodes(function, scope) if self.target else [])

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
                self.value.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target else None,
            ),
        )


@Parser.register
class CallAssembly(AbstractCallAssembly):
    # CALL ['PARTIAL' | 'MACRO'] <call target> (<args>) [-> <target>]
    NAME = "CALL"

    class IArg(AbstractAccessExpression, abc.ABC):
        __slots__ = ("source", "is_dynamic")

        def __init__(
            self,
            source: typing.Union["AbstractAccessExpression", IdentifierToken],
            is_dynamic: bool = False,
        ):
            self.source = source
            self.is_dynamic = is_dynamic

        def __repr__(self):
            return f"{type(self).__name__}{'' if not self.is_dynamic else 'Dynamic'}({self.source})"

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.source == other.source
                and self.is_dynamic == other.is_dynamic
            )

        def copy(self):
            return type(self)(self.source.copy(), self.is_dynamic)

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
            parents: list,
        ):
            return visitor(
                self, (self.source.visit_parts(visitor, parents + [self]),), parents
            )

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            return self.source.emit_bytecodes(function, scope)

        def emit_store_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            return self.source.emit_store_bytecodes(function, scope)

    class Arg(IArg):
        pass

    class StarArg(IArg):
        pass

    class KwArg(IArg):
        __slots__ = ("key", "source", "is_dynamic")

        def __init__(
            self,
            key: IdentifierToken | str,
            source: typing.Union["AbstractAccessExpression", IdentifierToken],
            is_dynamic: bool = False,
        ):
            self.key = key if isinstance(key, IdentifierToken) else IdentifierToken(key)
            super().__init__(source, is_dynamic=is_dynamic)

        def __repr__(self):
            return f"{type(self).__name__}{'' if not self.is_dynamic else 'Dynamic'}({self.key.text} = {self.source})"

        def __eq__(self, other):
            return (
                type(self) == type(other)
                and self.source == other.source
                and self.key == other.key
                and self.is_dynamic == other.is_dynamic
            )

        def copy(self):
            return type(self)(self.key, self.source.copy(), self.is_dynamic)

    class KwArgStar(IArg):
        pass

    @classmethod
    def construct_from_partial(cls, access: AbstractAccessExpression, parser: "Parser", scope: ParsingScope):
        return cls.consume_inner(parser, False, False, scope, call_target=access, allow_target=False)

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "CallAssembly":
        is_partial = bool(parser.try_consume(IdentifierToken("PARTIAL")))
        is_macro = not is_partial and bool(parser.try_consume(IdentifierToken("MACRO")))
        return cls.consume_inner(parser, is_partial, is_macro, scope)

    @classmethod
    def consume_inner(
        cls, parser: Parser, is_partial: bool, is_macro: bool, scope: ParsingScope, call_target=None, allow_target=True
    ) -> "CallAssembly":
        if call_target is None:
            if not is_macro:
                call_target = parser.try_parse_data_source(include_bracket=False, scope=scope, allow_calls=False)

                if isinstance(call_target, AbstractCallAssembly):
                    raise RuntimeError

            else:
                name = [parser.consume(IdentifierToken, err_arg=scope)]

                while parser.try_consume(SpecialToken(":")):
                    name.append(parser.consume(IdentifierToken, err_arg=scope))

                call_target = MacroAccessExpression(name)

        if call_target is None:
            raise throw_positioned_syntax_error(
                scope,
                parser.try_inspect(),
                "expected <expression> to be called (did you forget the prefix?)"
                if not is_macro
                else "expected <macro name>",
            )

        args: typing.List[CallAssembly.IArg] = []

        parser.consume(SpecialToken("("), err_arg=scope)

        has_seen_keyword_arg = False

        while not (bracket := parser.try_consume(SpecialToken(")"))):
            if (
                isinstance(parser[0], IdentifierToken)
                and parser[1] == SpecialToken("=")
                and not is_macro
            ):
                key = parser.consume(IdentifierToken)
                parser.consume(SpecialToken("="))

                is_dynamic = is_partial and bool(parser.try_consume(SpecialToken("?")))

                expr = parser.try_parse_data_source(
                    allow_primitives=True, include_bracket=False
                )

                args.append(CallAssembly.KwArg(key, expr, is_dynamic))

                has_seen_keyword_arg = True

            elif parser[0].text == "*" and not is_macro:
                if parser[1] == SpecialToken("*"):
                    parser.consume(SpecialToken("*"))
                    parser.consume(SpecialToken("*"))
                    expr = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False
                    )
                    args.append(CallAssembly.KwArgStar(expr))
                    has_seen_keyword_arg = True

                elif not has_seen_keyword_arg:
                    parser.consume(SpecialToken("*"))
                    expr = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False
                    )
                    args.append(CallAssembly.StarArg(expr))

                else:
                    raise throw_positioned_syntax_error(
                        scope,
                        parser.try_inspect(),
                        "*<arg> only allowed before keyword arguments!",
                    )

            elif not has_seen_keyword_arg:
                if is_macro and parser[0] == SpecialToken("{"):
                    expr = parser.parse_body(scope=scope)
                    is_dynamic = False
                else:
                    is_dynamic = is_partial and bool(
                        parser.try_consume(SpecialToken("?"))
                    )

                    expr = parser.try_consume_access_to_value(allow_primitives=True)

                    if expr is None:
                        if parser[0] == SpecialToken(")"):
                            break

                        raise throw_positioned_syntax_error(
                            scope, parser[0], "<expression> expected"
                        )

                args.append(CallAssembly.Arg(expr, is_dynamic))

            else:
                raise throw_positioned_syntax_error(
                    scope,
                    parser.try_inspect(),
                    "pure <arg> only allowed before keyword arguments",
                )

            if not parser.try_consume(SpecialToken(",")):
                break

        if bracket is None and not parser.try_consume(SpecialToken(")")):
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected ')'"
            )

        if allow_target and parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        return cls(call_target, args, target, is_partial, is_macro)

    @classmethod
    def consume_macro_call(cls, parser: Parser, scope) -> "CallAssembly":
        return cls.consume_inner(parser, False, True, scope)

    def __init__(
        self,
        call_target: AbstractSourceExpression,
        args: typing.List["CallAssembly.IArg"],
        target: AbstractAccessExpression | None = None,
        is_partial: bool = False,
        is_macro: bool = False,
    ):
        self.call_target = call_target
        self.args = args
        self.target = target
        self.is_partial = is_partial
        self.is_macro = is_macro

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
                self.call_target.visit_parts(
                    visitor,
                    parents + [self],
                ),
                [
                    arg.visit_parts(
                        visitor,
                        parents + [self],
                    )
                    for arg in self.args
                ],
                self.target.visit_parts(
                    visitor,
                    parents + [self],
                )
                if self.target
                else None,
            ),
            parents,
        )

    def copy(self) -> "CallAssembly":
        return CallAssembly(
            self.call_target.copy(),
            [arg.copy() for arg in self.args],
            self.target.copy() if self.target else None,
            self.is_partial,
            self.is_macro,
        )

    def __repr__(self):
        return f"CALL{('' if not self.is_macro else '-MACRO') if not self.is_partial else '-PARTIAL'}({self.call_target}, ({repr(self.args)[1:-1]}){', ' + repr(self.target) if self.target else ''})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.call_target == other.call_target
            and self.args == other.args
            and self.target == other.target
            and self.is_partial == other.is_partial
            and self.is_macro == other.is_macro
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.is_macro:
            return self.emit_macro_bytecode(function, scope)

        has_seen_star = False
        has_seen_star_star = False
        has_seen_kw_arg = False

        for arg in self.args:
            if isinstance(arg, CallAssembly.KwArg):
                has_seen_kw_arg = True

            elif isinstance(arg, CallAssembly.KwArgStar):
                has_seen_star_star = True

            elif isinstance(arg, CallAssembly.StarArg):
                has_seen_star = True

        if not has_seen_kw_arg and not has_seen_star and not has_seen_star_star:
            if self.is_partial:
                bytecode = [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial)
                ]
                extra_args = 1
            else:
                bytecode = []
                extra_args = 0

            bytecode += self.call_target.emit_bytecodes(function, scope)

            for arg in self.args:
                bytecode += arg.source.emit_bytecodes(function, scope)

            bytecode += [
                Instruction(
                    function, -1, "CALL_FUNCTION", arg=len(self.args) + extra_args
                ),
            ]

        elif has_seen_kw_arg and not has_seen_star and not has_seen_star_star:
            if self.is_partial:
                bytecode = [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial)
                ]
                extra_args = 1
            else:
                bytecode = []
                extra_args = 0

            bytecode += self.call_target.emit_bytecodes(function, scope)

            kw_arg_keys = []

            for arg in reversed(self.args):
                bytecode += arg.source.emit_bytecodes(function, scope)

                if isinstance(arg, CallAssembly.KwArg):
                    kw_arg_keys.append(arg.key.text)

                kw_const = tuple(reversed(kw_arg_keys))

                bytecode += [
                    Instruction(function, -1, "LOAD_CONST", kw_const),
                    Instruction(
                        function,
                        -1,
                        "CALL_FUNCTION_KW",
                        arg=len(self.args) + extra_args,
                    ),
                ]

        else:
            bytecode = self.call_target.emit_bytecodes(function, scope)

            bytecode += [Instruction(function, -1, "BUILD_LIST", arg=0)]

            if self.is_partial:
                bytecode += [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial),
                    Instruction(function, -1, "LIST_APPEND"),
                ]

            i = -1
            for i, arg in enumerate(self.args):
                bytecode += arg.source.emit_bytecodes(function, scope)

                if isinstance(arg, CallAssembly.Arg):
                    bytecode += [Instruction(function, -1, "LIST_APPEND", arg=1)]
                elif isinstance(arg, CallAssembly.StarArg):
                    bytecode += [Instruction(function, -1, "LIST_EXTEND", arg=1)]
                else:
                    break

            bytecode += [
                Instruction(function, -1, "LIST_TO_TUPLE"),
            ]

            if has_seen_kw_arg or has_seen_star_star:
                bytecode += [Instruction(function, -1, "BUILD_MAP", arg=0)]

                for arg in self.args[i + 1 :]:
                    if isinstance(arg, CallAssembly.KwArg):
                        bytecode += (
                            [Instruction(function, -1, "LOAD_CONST", arg.key.text)]
                            + arg.source.emit_bytecodes(function, scope)
                            + [
                                Instruction(function, -1, "BUILD_MAP", arg=1),
                                Instruction(function, -1, "DICT_MERGE", arg=1),
                            ]
                        )
                    else:
                        bytecode += arg.source.emit_bytecodes(function, scope) + [
                            Instruction(function, -1, "DICT_MERGE", arg=1)
                        ]

            bytecode += [
                Instruction(
                    function,
                    -1,
                    "CALL_FUNCTION_EX",
                    arg=int(has_seen_kw_arg or has_seen_star_star),
                ),
            ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)

        return bytecode

    def emit_macro_bytecode(self, function: MutableFunction, scope: ParsingScope):
        access = typing.cast(MacroAccessExpression, self.call_target)
        name = access.name

        macro_declaration = scope.lookup_name_in_scope(name[0].text)

        if macro_declaration is None:
            raise throw_positioned_syntax_error(
                scope,
                typing.cast(MacroAccessExpression, self.call_target).name,
                f"Macro '{':'.join(map(lambda e: e.text, name))}' not found!",
                NameError,
            )

        if len(name) > 1:
            for e in name[1:]:
                macro_declaration = macro_declaration[e.text]

        if not isinstance(macro_declaration, MacroAssembly.MacroOverloadPage):
            raise RuntimeError(
                f"Expected Macro Declaration for '{':'.join(map(lambda e: e.text, name))}', got {macro_declaration}"
            )

        macro, args = macro_declaration.lookup([arg.source for arg in self.args], scope)

        if self.target is not None and macro.return_type is None:
            raise RuntimeError(
                f"Expected <return type> declaration at macro if using '->' in call"
            )

        bytecode = macro.emit_call_bytecode(function, scope, args)

        if self.target:
            bytecode += self.target.emit_bytecodes(function, scope)

        return bytecode


MacroAssembly.consume_call = CallAssembly.consume_macro_call


@Parser.register
class PopElementAssembly(AbstractAssemblyInstruction):
    # POP [<count>]
    NAME = "POP"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "PopElementAssembly":
        count = parser.try_consume(IntegerToken)
        return cls(count if count is not None else IntegerToken("1"))

    def __init__(self, count: IntegerToken):
        self.count = count

    def __eq__(self, other):
        return type(self) == type(other) and self.count == other.count

    def __repr__(self):
        return f"POP(#{self.count.text})"

    def copy(self) -> "PopElementAssembly":
        return PopElementAssembly(self.count)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "POP_TOP", int(self.count.text))
            for _ in range(int(self.count.text))
        ]


@Parser.register
class ReturnAssembly(AbstractAssemblyInstruction):
    # RETURN [<expr>]
    NAME = "RETURN"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "ReturnAssembly":
        return cls(
            parser.try_parse_data_source(
                allow_primitives=True, allow_op=True, include_bracket=False
            )
        )

    def __init__(self, expr: AbstractSourceExpression | None = None):
        self.expr = expr

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
            (self.expr.visit_parts(visitor, parents + [self]) if self.expr else None,),
            parents,
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.expr == other.expr

    def __repr__(self):
        return f"RETURN({self.expr})"

    def copy(self) -> "ReturnAssembly":
        return ReturnAssembly(self.expr.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        expr_bytecode = self.expr.emit_bytecodes(function, scope) if self.expr else []

        return expr_bytecode + [Instruction(function, -1, "RETURN_VALUE")]


@Parser.register
class MacroReturnAssembly(AbstractAssemblyInstruction):
    NAME = "MACRO_RETURN"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "ReturnAssembly":
        return cls(
            parser.try_parse_data_source(
                allow_primitives=True, allow_op=True, include_bracket=False
            )
        )

    def __init__(self, expr: AbstractSourceExpression | None = None):
        self.expr = expr

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
            (self.expr.visit_parts(visitor, parents + [self]) if self.expr else None,),
            parents,
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.expr == other.expr

    def __repr__(self):
        return f"MACRO_RETURN({self.expr})"

    def copy(self) -> "MacroReturnAssembly":
        return MacroReturnAssembly(self.expr.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        expr_bytecode = self.expr.emit_bytecodes(function, scope) if self.expr else []

        return expr_bytecode + [Instruction(function, -1, Opcodes.MACRO_RETURN_VALUE)]


@Parser.register
class YieldAssembly(AbstractAssemblyInstruction):
    # YIELD [*] [<expr>] [-> <target>]
    NAME = "YIELD"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "YieldAssembly":
        is_star = bool(parser.try_consume(SpecialToken("*")))

        expr = parser.try_parse_data_source(
            allow_primitives=True, allow_op=True, include_bracket=False
        )

        if parser.try_consume(SpecialToken("-")) and parser.try_consume(
            SpecialToken(">")
        ):
            target = parser.try_parse_data_source(
                allow_primitives=True, allow_op=True, include_bracket=False
            )

            if target is None:
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected <expression>"
                )

        else:
            target = None

        return cls(expr, is_star, target)

    def __init__(
        self,
        expr: AbstractSourceExpression | None = None,
        is_star: bool = False,
        target: AbstractSourceExpression | None = None,
    ):
        self.expr = expr
        self.is_star = is_star
        self.target = target

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
                self.expr.visit_parts(visitor, parents + [self]) if self.expr else None,
                self.target.visit_parts(
                    visitor,
                    parents + [self],
                )
                if self.target
                else None,
            ),
            parents,
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.expr == other.expr
            and self.is_star == other.is_star
            and self.target == other.target
        )

    def __repr__(self):
        return f"YIELD{'' if not self.is_star else '*'}({self.expr if self.expr else ''}{(', ' if self.expr else '->') + repr(self.target) if self.target else ''})"

    def copy(self) -> "YieldAssembly":
        return YieldAssembly(
            self.expr.copy() if self.expr else None,
            self.is_star,
            self.target.copy() if self.target else None,
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        bytecode = []

        if self.expr:
            bytecode += self.expr.emit_bytecodes(function, scope)

        if self.is_star:
            bytecode += [
                Instruction(function, -1, Opcodes.GET_YIELD_FROM_ITER),
                Instruction(function, -1, Opcodes.LOAD_CONST, None),
                Instruction(function, -1, Opcodes.YIELD_FROM),
            ]

        else:
            bytecode += [
                Instruction(function, -1, Opcodes.YIELD_VALUE),
            ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)

        else:
            bytecode += [Instruction(function, -1, Opcodes.POP_TOP)]

        # print(bytecode)

        return bytecode


@Parser.register
class JumpAssembly(AbstractAssemblyInstruction):
    # JUMP <label name> [(IF <condition access>) | ('(' <expression> | <op expression> ')')]
    NAME = "JUMP"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "JumpAssembly":
        has_quotes = parser.try_consume(SpecialToken("'"))

        label_target = parser.consume(IdentifierToken)

        if has_quotes:
            parser.consume(SpecialToken("'"))

        if parser.try_consume(IdentifierToken("IF")):
            condition = parser.try_parse_data_source(
                allow_primitives=True, include_bracket=False, allow_op=True
            )

        elif parser.try_consume(SpecialToken("(")):
            parser.save()
            condition = parser.try_parse_data_source(
                allow_primitives=True, include_bracket=False, allow_op=True
            )

            if condition is None or not parser.try_consume(SpecialToken(")")):
                parser.rollback()
                condition = OpAssembly.consume(parser, None)
                parser.consume(SpecialToken(")"))
            else:
                parser.discard_save()

        else:
            condition = None

        return cls(label_target, condition)

    def __init__(
        self,
        label_name_token: IdentifierToken | str,
        condition: AbstractAccessExpression | None = None,
    ):
        self.label_name_token = (
            label_name_token
            if isinstance(label_name_token, IdentifierToken)
            else IdentifierToken(label_name_token)
        )
        self.condition = condition

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
                self.condition.visit_parts(visitor, parents + [self])
                if self.condition
                else None,
            ),
            parents,
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.label_name_token == other.label_name_token
            and self.condition == other.condition
        )

    def __repr__(self):
        return f"JUMP({self.label_name_token.text}{'' if self.condition is None else ', IF '+repr(self.condition)})"

    def copy(self) -> "JumpAssembly":
        return JumpAssembly(
            self.label_name_token, self.condition.copy() if self.condition else None
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if not scope.exists_label(self.label_name_token.text):
            raise ValueError(
                f"Label '{self.label_name_token.text}' is not valid in this context!"
            )

        if self.condition is None:
            return [
                Instruction(
                    function,
                    -1,
                    Opcodes.JUMP_ABSOLUTE,
                    JumpToLabel(self.label_name_token.text),
                )
            ]

        return self.condition.emit_bytecodes(function, scope) + [
            Instruction(
                function,
                -1,
                Opcodes.POP_JUMP_IF_TRUE,
                JumpToLabel(self.label_name_token.text),
            )
        ]


@Parser.register
class FunctionDefinitionAssembly(AbstractAssemblyInstruction):
    # DEF [<func name>] ['<' ['!'] <bound variables\> '>'] '(' <signature> ')' ['->' <target>] '{' <body> '}'
    NAME = "DEF"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "FunctionDefinitionAssembly":
        func_name = parser.try_consume(IdentifierToken)
        bound_variables: typing.List[typing.Tuple[int, IdentifierToken, bool]] = []
        args = []

        if parser.try_consume(SpecialToken("<")):
            is_static = bool(parser.try_consume(SpecialToken("!")))

            expr = parser.try_consume(IdentifierToken)

            if expr:
                bound_variables.append((0, expr, is_static))

            while True:
                if parser.try_consume(SpecialToken("&")):
                    if not (expr := parser.try_consume(IdentifierToken)):
                        raise throw_positioned_syntax_error(
                            scope,
                            parser[0],
                            "Expected <identifier> after '&'"
                        )

                    bound_variables.append((1, expr, is_static))

                if not parser.try_consume(SpecialToken(",")) or not (
                    expr := parser.try_consume(IdentifierToken)
                ):
                    break

                bound_variables.append((0, expr, is_static))

            parser.consume(SpecialToken(">"), err_arg=scope)

        parser.consume(SpecialToken("("), err_arg=scope)

        while parser.try_inspect() != SpecialToken(")"):
            arg = None

            star = parser.try_consume(SpecialToken("*"))
            star_star = parser.try_consume(SpecialToken("*"))
            identifier = parser.try_consume(IdentifierToken)

            if not identifier:
                if star:
                    raise throw_positioned_syntax_error(
                        scope,
                        [star, star_star],
                        "Expected <expression> after '*'" if not star_star else "Expected <expression> after '**'"
                    )

                break

            if not star:
                if parser.try_consume(SpecialToken("=")):
                    default_value = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False, allow_op=True
                    )

                    if default_value is None:
                        raise SyntaxError

                    arg = CallAssembly.KwArg(identifier, default_value)

            if not arg:
                if star_star:
                    arg = CallAssembly.KwArgStar(identifier)
                elif star:
                    arg = CallAssembly.StarArg(identifier)
                else:
                    arg = CallAssembly.Arg(identifier)

            args.append(arg)

            if not parser.try_consume(SpecialToken(",")):
                break

        parser.consume(SpecialToken(")"))

        if expr := parser.try_consume(SpecialToken("<")):
            raise throw_positioned_syntax_error(
                scope,
                expr,
                "Respect ordering (got 'args' before 'captured'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }",
            )

        if parser.try_consume(SpecialToken("-")) and parser.try_consume(
            SpecialToken(">")
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        body = parser.parse_body(scope=scope)

        if expr := parser.try_consume(SpecialToken("-")):
            raise throw_positioned_syntax_error(
                scope,
                expr,
                "Respect ordering (got 'code' before 'target'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }",
            )

        return cls(func_name, bound_variables, args, body, target)

    def __init__(
        self,
        func_name: IdentifierToken | str | None,
        bound_variables: typing.List[typing.Tuple[int, IdentifierToken | str, bool] | str],
        args: typing.List[CallAssembly.IArg],
        body: CompoundExpression,
        target: AbstractAccessExpression | None = None,
    ):
        self.func_name = (
            func_name if not isinstance(func_name, str) else IdentifierToken(func_name)
        )
        self.bound_variables: typing.List[typing.Tuple[int, IdentifierToken, bool]] = []
        # var if isinstance(var, IdentifierToken) else IdentifierToken(var) for var in bound_variables]

        for element in bound_variables:
            if isinstance(element, str):
                self.bound_variables.append(
                    (
                        0,
                        IdentifierToken(element.removeprefix("!")),
                        element.startswith("!"),
                    )
                )
            elif isinstance(element, tuple):
                if len(element) == 3:
                    a_type, token, is_static = element
                else:
                    a_type = 0
                    token, is_static = element

                if isinstance(token, str):
                    self.bound_variables.append((a_type, IdentifierToken(token), is_static))
                else:
                    self.bound_variables.append(element)
            else:
                raise ValueError(element)

        self.args = args
        self.body = body
        self.target = target

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
        return f"DEF({self.func_name.text}<{repr(self.bound_variables)[1:-1]}>({repr(self.args)[1:-1]}){'-> ' + repr(self.target) if self.target else ''} {{ {self.body} }})"

    def copy(self) -> "FunctionDefinitionAssembly":
        return FunctionDefinitionAssembly(
            self.func_name,
            self.bound_variables.copy(),
            [arg.copy() for arg in self.args],
            self.body.copy(),
            self.target.copy() if self.target else None,
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        flags = 0
        bytecode = []

        inner_labels = self.body.collect_label_info()
        label_targets = {}

        inner_scope = scope.copy()

        target = MutableFunction(lambda: None)
        inner_bytecode = self.body.emit_bytecodes(target, inner_scope)
        inner_bytecode[-1].next_instruction = target.instructions[0]

        for i, instr in enumerate(inner_bytecode[:-1]):
            instr.next_instruction = inner_bytecode[i + 1]

        def walk_label(instruction: Instruction):
            if instruction.opcode == Opcodes.BYTECODE_LABEL:
                # print(instruction, instruction.next_instruction)
                label_targets[instruction.arg_value] = instruction.next_instruction if instruction.next_instruction is not None else instruction
                instruction.change_opcode(Opcodes.NOP, update_next=False)

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(walk_label))

        def resolve_jump_to_label(ins: Instruction):
            if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
                ins.change_arg_value(label_targets[ins.arg_value.name])

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(resolve_jump_to_label))

        target.assemble_instructions_from_tree(inner_bytecode[0])
        del inner_bytecode

        has_kwarg = False
        for arg in self.args:
            if isinstance(arg, CallAssembly.KwArg):
                has_kwarg = True
                break

        if has_kwarg:
            flags |= 0x02
            raise NotImplementedError("Kwarg defaults")

        if self.bound_variables:
            if any(map(lambda e: e[2], self.bound_variables)):
                raise NotImplementedError("Static variables")

            flags |= 0x08

            macro_params = tuple()

            for is_macro, name, is_static in self.bound_variables:
                if is_macro == 0:
                    if name not in scope.macro_parameter_namespace:
                        raise RuntimeError

                    param = scope.macro_parameter_namespace[name]

                    if not isinstance(param, (GlobalAccessExpression, LocalAccessExpression)):
                        raise RuntimeError(param)

                    macro_params += (param.name_token.text,)

            bytecode += [
                Instruction(
                    function,
                    -1,
                    "LOAD_CONST",
                    tuple((e[1] for e in self.bound_variables if e[0] == 0)) + macro_params,
                ),
            ]

        target.argument_count = len(self.args)
        code_object = target.create_code_obj()

        bytecode += [
            Instruction(function, -1, "LOAD_CONST", code_object),
            Instruction(
                function,
                -1,
                "LOAD_CONST",
                self.func_name.text if self.func_name else "<lambda>",
            ),
            Instruction(function, -1, "MAKE_FUNCTION", arg=flags),
        ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)
        else:
            bytecode += [
                Instruction(function, -1, Opcodes.STORE_FAST, self.func_name.text),
            ]

        return bytecode


@Parser.register
class ClassDefinitionAssembly(AbstractAssemblyInstruction):
    # CLASS <name> ['(' [<parent> {',' <parent>}] ')'] '{' ... '}'
    NAME = "CLASS"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "ClassDefinitionAssembly":
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
        self,
        name_token: IdentifierToken,
        parents: typing.List[AbstractAccessExpression],
        code_block: CompoundExpression,
    ):
        self.name_token = name_token
        self.parents = parents
        self.code_block = code_block

    def __repr__(self):
        return f"ClassAssembly::'{self.name_token.text}'({','.join(map(repr, self.parents))}){{{self.code_block}}}"

    def copy(self):
        return ClassDefinitionAssembly(
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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        inner_scope = scope.copy(sub_scope_name=self.name_token.text)

        target = MutableFunction(lambda: None)

        inner_bytecode = [
            Instruction(target, -1, Opcodes.LOAD_NAME, "__name__"),
            Instruction(target, -1, Opcodes.STORE_NAME, "__module__"),
            Instruction(target, -1, Opcodes.LOAD_CONST, self.name_token.text),
            Instruction(target, -1, Opcodes.STORE_NAME, "__qualname__"),
        ]

        raw_inner_code = self.code_block.emit_bytecodes(target, inner_scope)

        for instr in raw_inner_code:
            if instr.opcode == Opcodes.LOAD_FAST:
                instr.change_opcode(Opcodes.LOAD_NAME, arg_value=instr.arg_value)
            elif instr.opcode == Opcodes.STORE_FAST:
                instr.change_opcode(Opcodes.STORE_NAME, arg_value=instr.arg_value)
            elif instr.opcode == Opcodes.DELETE_FAST:
                instr.change_opcode(Opcodes.DELETE_NAME, arg_value=instr.arg_value)

        inner_bytecode += raw_inner_code

        if inner_bytecode:
            inner_bytecode[-1].next_instruction = target.instructions[0]

        for i, instr in enumerate(inner_bytecode[:-1]):
            instr.next_instruction = inner_bytecode[i + 1]

        target.assemble_instructions_from_tree(inner_bytecode[0])
        target.reassign_to_function()

        code_obj = target.target.__code__

        bytecode = [
            Instruction(function, -1, Opcodes.LOAD_BUILD_CLASS),
            Instruction(function, -1, Opcodes.LOAD_CONST, code_obj),
            Instruction(function, -1, Opcodes.LOAD_CONST, self.name_token.text),
            Instruction(function, -1, Opcodes.MAKE_FUNCTION, arg=0),
            Instruction(function, -1, Opcodes.LOAD_CONST, self.name_token.text),
        ]

        for parent in self.parents:
            bytecode += parent.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2 + len(self.parents)),
            Instruction(function, -1, Opcodes.STORE_FAST, self.name_token.text),
        ]
        return bytecode


@Parser.register
class ForEachAssembly(AbstractAssemblyInstruction):
    # FOREACH <variable> {',' <variable>} IN <iterable> {(',' | '*') <iterable>} '{' <block> '}'
    NAME = "FOREACH"

    class ForEachMultiplier(AbstractAccessExpression):
        def __init__(self, *items: AbstractAccessExpression):
            self.items = list(items)

        def emit_bytecodes(
            self, function: MutableFunction, scope: ParsingScope
        ) -> typing.List[Instruction]:
            bytecode = [
                Instruction(function, -1, Opcodes.LOAD_CONST, itertools.product),
            ]

            for item in self.items:
                bytecode += item.emit_bytecodes(function, scope)

            bytecode += [
                Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=len(self.items)),
            ]
            return bytecode

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "ForEachAssembly":
        initial = parser.try_consume_access_to_value()
        if initial is None:
            raise throw_positioned_syntax_error(
                scope,
                parser[0],
                "<expression> expected"
            )
        variables = [initial]


        while parser.try_consume(SpecialToken(",")):

            expr = parser.try_consume_access_to_value()

            if expr is None:
                raise throw_positioned_syntax_error(
                    scope,
                    parser[0],
                    "<expression> expected"
                )

            variables.append(expr)

        if not parser.try_consume(IdentifierToken("IN")):
            raise throw_positioned_syntax_error(
                scope,
                parser[0],
                "'IN' expected"
            )

        source = parser.try_consume_access_to_value()
        if not source:
            raise throw_positioned_syntax_error(
                scope,
                parser[0],
                "<expression> expected"
            )
        sources = [source]

        multi = None
        while parser.try_consume(SpecialToken(",")) or (multi := parser.try_consume(SpecialToken("*"))):
            source = parser.try_consume_access_to_value()
            if not source:
                raise throw_positioned_syntax_error(
                    scope,
                    parser[0],
                    "<expression> expected"
                )

            if multi:
                s = sources[-1]

                if isinstance(s, cls.ForEachMultiplier):
                    s.items.append(source)
                else:
                    sources[-1] = cls.ForEachMultiplier(s, source)

                multi = None
            else:
                sources.append(source)

        if len(variables) != len(sources):
            raise throw_positioned_syntax_error(
                scope,
                scope.last_base_token,
                f"Number of Variables ({len(variables)}) must equal number of Sources ({len(sources)})"
            )

        body = parser.parse_body(scope=scope)
        return cls(
            variables,
            sources,
            body,
            scope.last_base_token,
        )

    def __init__(self, variables: typing.List[AbstractSourceExpression], sources: typing.List[AbstractSourceExpression], body: CompoundExpression, base_token: AbstractToken = None):
        self.variables = variables
        self.sources = sources
        self.body = body
        self.base_token = base_token

    def copy(self):
        return type(self)(
            [var.copy() for var in self.variables],
            [source.copy() for source in self.sources],
            self.body.copy(),
        )

    def __repr__(self):
        entries = ", ".join(
            [
                f"{source} -> {var}"
                for var, source in zip(self.variables, self.sources)
            ]
        )
        return f"FOREACH({entries})"

    def __eq__(self, other):
        return type(self) == type(other) and self.variables == other.variables and self.sources == other.sources and self.body == other.body

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if len(self.variables) != 1:
            bytecode = [
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.LOAD_CONST, zip),
            ]
        else:
            bytecode = []

        for source in self.sources:
            bytecode += source.emit_bytecodes(function, scope)

        loop_label_name_enter = scope.scope_name_generator("foreach_loop_enter")
        loop_label_name_exit = scope.scope_name_generator("foreach_loop_exit")

        if len(self.variables) != 1:
            bytecode += [
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.CALL_FUNCTION, arg=len(self.sources)),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.GET_ITER),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.BYTECODE_LABEL, loop_label_name_enter),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.FOR_ITER, JumpToLabel(loop_label_name_exit)),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.UNPACK_SEQUENCE, arg=len(self.sources)),
            ]
        else:
            bytecode += [
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.GET_ITER),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.BYTECODE_LABEL, loop_label_name_enter),
                Instruction.create_with_token(self.base_token, function, -1, Opcodes.FOR_ITER, JumpToLabel(loop_label_name_exit)),
            ]

        for var in self.variables:
            bytecode += var.emit_store_bytecodes(function, scope)

        bytecode += self.body.emit_bytecodes(function, scope)

        bytecode += [
            Instruction.create_with_token(self.base_token, function, -1, Opcodes.JUMP_ABSOLUTE, JumpToLabel(loop_label_name_enter)),
            Instruction.create_with_token(self.base_token, function, -1, Opcodes.BYTECODE_LABEL, loop_label_name_exit),
        ]

        return bytecode

