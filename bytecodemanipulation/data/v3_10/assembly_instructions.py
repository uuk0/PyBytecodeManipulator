import abc
import functools
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
)
from bytecodemanipulation.assembler.Lexer import (
    SpecialToken,
    IdentifierToken,
    IntegerToken,
)
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction


@Parser.register
class LoadAssembly(AbstractAssemblyInstruction):
    # LOAD <access> [-> <target>]
    NAME = "LOAD"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadAssembly":
        access = parser.try_consume_access_token(allow_tos=False, allow_primitives=True)

        if access is None:
            raise SyntaxError(parser.try_inspect())

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_token()
        else:
            target = None

        return cls(access, target)

    def __init__(
        self,
        access_token: AbstractAccessExpression,
        target: AbstractAccessExpression | None = None,
    ):
        self.access_token = access_token
        self.target = target

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.access_token == other.access_token
            and self.target == other.target
        )

    def __repr__(self):
        return f"LOAD({self.access_token}{', ' + repr(self.target) if self.target else ''})"

    def copy(self) -> "LoadAssembly":
        return LoadAssembly(self.access_token, self.target)

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return self.access_token.emit_bytecodes(function, labels) + (
            self.target.emit_bytecodes(function, labels) if self.target else []
        )

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.access_token.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target is not None else None,
            ),
        )

@Parser.register
class StoreAssembly(AbstractAssemblyInstruction):
    # STORE <access> [(expression)]
    NAME = "STORE"

    @classmethod
    def consume(cls, parser: "Parser") -> "StoreAssembly":
        access = parser.try_consume_access_token(allow_tos=False)

        if access is None:
            raise SyntaxError

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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return (
            [] if self.source is None else self.source.emit_bytecodes(function, labels)
        ) + self.access_token.emit_store_bytecodes(function)

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.access_token.visit_parts(visitor),
                self.source.visit_parts(visitor) if self.source is not None else None,
            ),
        )


@Parser.register
class OpAssembly(AbstractAssemblyInstruction, AbstractAccessExpression):
    """
    OP ... [-> <target>]
    - <expr> +|-|*|/|//|**|%|&|"|"|^|>>|<<|@ <expr>
    """

    NAME = "OP"

    BINARY_OPS: typing.Dict[str, typing.Tuple[int, int] | int] = {
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
        "nis": (Opcodes.IS_OP, 1),
        "in": (Opcodes.CONTAINS_OP, 0),
        "nin": (Opcodes.CONTAINS_OP, 1),
        "<": (Opcodes.COMPARE_OP, 0),
        "<=": (Opcodes.COMPARE_OP, 1),
        "==": (Opcodes.COMPARE_OP, 2),
        "!=": (Opcodes.COMPARE_OP, 3),
        ">": (Opcodes.COMPARE_OP, 4),
        ">=": (Opcodes.COMPARE_OP, 5),
        # todo: is there a better way?
        "xor": (Opcodes.COMPARE_OP, 3),
        "xnor": (Opcodes.COMPARE_OP, 2),
    }

    # todo: parse and implement
    SINGLE_OPS: typing.Dict[str, typing.Tuple[int, int] | int] = {
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

        def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
            raise NotImplementedError

        def __eq__(self, other):
            raise NotImplementedError

        def __repr__(self):
            raise NotImplementedError

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

        def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
            opcode_info = OpAssembly.BINARY_OPS[self.operator]

            if isinstance(opcode_info, int):
                opcode, arg = opcode_info, 0
            else:
                opcode, arg = opcode_info

            return (
                self.lhs.emit_bytecodes(function, labels)
                + self.rhs.emit_bytecodes(function, labels)
                + [Instruction(function, -1, opcode, arg=arg)]
            )

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            return visitor(
                self, (self.lhs.visit_parts(visitor), self.rhs.visit_parts(visitor))
            )

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

    @classmethod
    def consume(cls, parser: "Parser") -> "OpAssembly":
        if expr := cls.try_consume_binary(parser):
            return cls(expr, cls.try_consume_arrow(parser))

        raise SyntaxError

    @classmethod
    def try_consume_arrow(cls, parser: "Parser") -> AbstractAccessExpression | None:
        if parser.try_consume(SpecialToken("-")):
            parser.consume(SpecialToken(">"))
            return parser.try_consume_access_token()

    @classmethod
    def try_consume_binary(cls, parser: "Parser") -> typing.Optional[IOperation]:
        parser.save()

        lhs = parser.try_parse_data_source(allow_primitives=True, include_bracket=False)

        part = parser[0:2]

        if part:
            first, second = part
        else:
            first, second = parser[0], None

        if isinstance(first, IdentifierToken) and first.text in cls.BINARY_OPS:
            OP_NAME = first.text
            parser.consume(first)
        else:
            if not isinstance(first, SpecialToken):
                first = None

            if not isinstance(second, SpecialToken):
                second = None

            if first is None:
                print("lhs is None")
                parser.rollback()
                return

            OP_NAME = None

            if second:
                key = first.text + second.text

                if key in cls.BINARY_OPS:
                    OP_NAME = key
                    parser.consume(first)
                    parser.consume(second)

            if OP_NAME is None:
                if first.text in cls.BINARY_OPS:
                    OP_NAME = first.text
                    parser.consume(first)
                else:
                    return

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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return self.operation.emit_bytecodes(function, labels) + (
            [] if self.target is None else self.target.emit_bytecodes(function, labels)
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        raise RuntimeError("cannot assign to an operator!")

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (self.operation.visit_parts(visitor), self.target.visit_parts(visitor)),
        )


@Parser.register
class IFAssembly(AbstractAssemblyInstruction):
    # IF <expression> '{' <body> '}'
    NAME = "IF"

    @classmethod
    def consume(cls, parser: "Parser") -> "IFAssembly":
        return cls(
            parser.try_parse_data_source(allow_primitives=True, include_bracket=False),
            parser.parse_body(),
        )

    def __init__(self, source: AbstractSourceExpression, body: CompoundExpression):
        self.source = source
        self.body = body

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy())

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.body == other.body
        )

    def __repr__(self):
        return f"IF({self.source}) -> {{{self.body}}}"

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]):
        end = Instruction(function, -1, "NOP")
        return (
            self.source.emit_bytecodes(function, labels)
            + [Instruction(function, -1, "POP_JUMP_IF_FALSE", end)]
            + self.body.emit_bytecodes(function, labels)
            + [end]
        )

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, (self.source.visit_parts(visitor), self.body.visit_parts(visitor))
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))


@Parser.register
class WHILEAssembly(AbstractAssemblyInstruction):
    # WHILE <expression> '{' <body> '}'
    NAME = "WHILE"

    @classmethod
    def consume(cls, parser: "Parser") -> "WHILEAssembly":
        return cls(
            parser.try_parse_data_source(allow_primitives=True, include_bracket=False),
            parser.parse_body(),
        )

    def __init__(self, source: AbstractSourceExpression, body: CompoundExpression):
        self.source = source
        self.body = body

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy())

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.body == other.body
        )

    def __repr__(self):
        return f"WHILE({self.source}) -> {{{self.body}}}"

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]):
        end = Instruction(function, -1, "NOP")

        CONDITION = self.source.emit_bytecodes(function, labels)

        HEAD = Instruction(function, -1, "POP_JUMP_IF_FALSE", end)

        BODY = self.body.emit_bytecodes(function, labels)

        JUMP_BACK = Instruction(function, -1, "JUMP_ABSOLUTE", CONDITION[0])

        return CONDITION + [HEAD] + BODY + [JUMP_BACK, end]

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, (self.source.visit_parts(visitor), self.body.visit_parts(visitor))
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))


@Parser.register
class LoadGlobalAssembly(AbstractAssemblyInstruction):
    # LOAD_GLOBAL <name> [-> <target>]
    NAME = "LOAD_GLOBAL"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadGlobalAssembly":
        parser.try_consume(SpecialToken("@"))
        name = parser.consume([IdentifierToken, IntegerToken])

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_token()
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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_GLOBAL", value)] + (
            self.target.emit_bytecodes(function, labels) if self.target else []
        )

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, (self.target.visit_parts(visitor) if self.target else None,)
        )


@Parser.register
class StoreGlobalAssembly(AbstractAssemblyInstruction):
    # STORE_GLOBAL <name> [<source>]
    NAME = "STORE_GLOBAL"

    @classmethod
    def consume(cls, parser: "Parser") -> "StoreGlobalAssembly":
        parser.try_consume(SpecialToken("@"))
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
        return f"STORE_GLOBAL({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "StoreGlobalAssembly":
        return StoreGlobalAssembly(
            self.name, self.source.copy() if self.source else None
        )

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return ([] if self.source is None else self.source.emit_bytecodes(function, labels)) + [
            Instruction(function, -1, "STORE_GLOBAL", value)
        ]

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, (self.source.visit_parts(visitor) if self.target else None,)
        )


@Parser.register
class LoadFastAssembly(AbstractAssemblyInstruction):
    # LOAD_FAST <name> [-> <target>]
    NAME = "LOAD_FAST"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadFastAssembly":
        parser.try_consume(SpecialToken("$"))
        name = parser.consume([IdentifierToken, IntegerToken])

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_token()
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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_FAST", value)] + (
            self.target.emit_bytecodes(function, labels) if self.target else []
        )

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, (self.target.visit_parts(visitor) if self.target else None,)
        )


@Parser.register
class StoreFastAssembly(AbstractAssemblyInstruction):
    # STORE_FAST <name> [<source>]
    NAME = "STORE_FAST"

    @classmethod
    def consume(cls, parser: "Parser") -> "StoreFastAssembly":
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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return ([] if self.source is None else self.source.emit_bytecodes(function, labels)) + [
            Instruction(function, -1, "STORE_FAST", value)
        ]

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, (self.source.visit_parts(visitor) if self.target else None,)
        )


@Parser.register
class LoadConstAssembly(AbstractAssemblyInstruction):
    # LOAD_CONST <expression> | @<global const source> [-> <target>]
    NAME = "LOAD_CONST"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadConstAssembly":
        value = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False
        )

        if not isinstance(value, (ConstantAccessExpression, GlobalAccessExpression)):
            raise SyntaxError(value)

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_token()
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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return [
            Instruction(
                function,
                -1,
                "LOAD_CONST",
                self.value.value
                if isinstance(self.value, ConstantAccessExpression)
                else function.target.__globals__.get(self.value.name_token.text),
            )
        ] + (self.target.emit_bytecodes(function, labels) if self.target else [])

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.value.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target else None,
            ),
        )


@Parser.register
class CallAssembly(AbstractAssemblyInstruction):
    # CALL ['PARTIAL'] <call target> (<args>) [-> <target>]
    NAME = "CALL"

    class IArg(IAssemblyStructureVisitable, abc.ABC):
        __slots__ = ("source", "is_dynamic")

        def __init__(self, source: typing.Union["AbstractAccessExpression", IdentifierToken], is_dynamic: bool = False):
            self.source = source
            self.is_dynamic = is_dynamic

        def __repr__(self):
            return f"{type(self).__name__}{'' if not self.is_dynamic else 'Dynamic'}({self.source})"

        def __eq__(self, other):
            return type(self) == type(other) and self.source == other.source and self.is_dynamic == other.is_dynamic

        def copy(self):
            return type(self)(self.source.copy(), self.is_dynamic)

        def visit_parts(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            return visitor(self, (self.source.visit_parts(visitor),))

        def visit_assembly_instructions(
            self,
            visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any],
        ):
            pass

    class Arg(IArg):
        pass

    class StarArg(IArg):
        pass

    class KwArg(IArg):
        __slots__ = ("key", "source", "is_dynamic")

        def __init__(
            self, key: IdentifierToken | str, source: typing.Union["AbstractAccessExpression", IdentifierToken], is_dynamic: bool = False
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
    def consume(cls, parser: "Parser") -> "CallAssembly":
        is_partial = bool(parser.try_consume(IdentifierToken("PARTIAL")))

        call_target = parser.try_parse_data_source(include_bracket=False)

        args: typing.List[CallAssembly.IArg] = []

        parser.consume(SpecialToken("("))

        has_seen_keyword_arg = False

        while not (bracket := parser.try_consume(SpecialToken(")"))):
            if isinstance(parser[0], IdentifierToken) and parser[1] == SpecialToken(
                "="
            ):
                key = parser.consume(IdentifierToken)
                parser.consume(SpecialToken("="))

                is_dynamic = is_partial and bool(parser.try_consume(SpecialToken("?")))

                expr = parser.try_parse_data_source(
                    allow_primitives=True, include_bracket=False
                )

                args.append(CallAssembly.KwArg(key, expr, is_dynamic))

                has_seen_keyword_arg = True

            elif parser[0].text == "*":
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
                    raise SyntaxError("*<arg> only allowed before keyword arguments!")

            elif not has_seen_keyword_arg:
                is_dynamic = is_partial and bool(parser.try_consume(SpecialToken("?")))

                expr = parser.try_parse_data_source(
                    allow_primitives=True, include_bracket=False
                )
                args.append(CallAssembly.Arg(expr, is_dynamic))

            else:
                raise SyntaxError("pure <arg> only allowed before keyword arguments!")

            if not parser.try_consume(SpecialToken(",")):
                break

        if bracket is None and not parser.try_consume(SpecialToken(")")):
            raise SyntaxError(f"expected closing bracket, got {parser[0]}")

        if parser.try_consume_multi(
            [
                SpecialToken("-"),
                SpecialToken(">"),
            ]
        ):
            target = parser.try_consume_access_token()
        else:
            target = None

        return cls(call_target, args, target, is_partial)

    def __init__(
        self,
        call_target: AbstractAccessExpression,
        args: typing.List["CallAssembly.IArg"],
        target: AbstractAccessExpression | None = None,
        is_partial: bool = False,
    ):
        self.call_target = call_target
        self.args = args
        self.target = target
        self.is_partial = is_partial

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.call_target.visit_parts(visitor),
                [arg.visit_parts(visitor) for arg in self.args],
                self.target.visit_parts(visitor) if self.target else None,
            ),
        )

    def copy(self) -> "CallAssembly":
        return CallAssembly(
            self.call_target.copy(),
            [arg.copy() for arg in self.args],
            self.target.copy() if self.target else None,
            self.is_partial,
        )

    def __repr__(self):
        return f"CALL{'' if not self.is_partial else '-PARTIAL'}({self.call_target}, ({repr(self.args)[1:-1]}){', ' + repr(self.target) if self.target else ''})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.call_target == other.call_target
            and self.args == other.args
            and self.target == other.target
            and self.is_partial == other.is_partial
        )

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
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

            bytecode += self.call_target.emit_bytecodes(function, labels)

            for arg in self.args:
                bytecode += arg.source.emit_bytecodes(function, labels)

            bytecode += [
                Instruction(function, -1, "CALL_FUNCTION", arg=len(self.args) + extra_args),
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

            bytecode += self.call_target.emit_bytecodes(function, labels)

            kw_arg_keys = []

            for arg in reversed(self.args):
                bytecode += arg.source.emit_bytecodes(function, labels)

                if isinstance(arg, CallAssembly.KwArg):
                    kw_arg_keys.append(arg.key.text)

                kw_const = tuple(reversed(kw_arg_keys))

                bytecode += [
                    Instruction(function, -1, "LOAD_CONST", kw_const),
                    Instruction(function, -1, "CALL_FUNCTION_KW", arg=len(self.args) + extra_args),
                ]

        else:
            bytecode = self.call_target.emit_bytecodes(function, labels)

            bytecode += [Instruction(function, -1, "BUILD_LIST")]

            if self.is_partial:
                bytecode += [
                    Instruction(function, -1, Opcodes.LOAD_CONST, functools.partial),
                    Instruction(function, -1, "LIST_APPEND"),
                ]

            i = -1
            for i, arg in enumerate(self.args):
                bytecode += arg.source.emit_bytecodes(function, labels)

                if isinstance(arg, CallAssembly.Arg):
                    bytecode += [Instruction(function, -1, "LIST_APPEND")]
                elif isinstance(arg, CallAssembly.StarArg):
                    bytecode += [Instruction(function, -1, "LIST_EXTEND")]
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
                            + arg.source.emit_bytecodes(function, labels)
                            + [
                                Instruction(function, -1, "BUILD_MAP", arg=1),
                                Instruction(function, -1, "DICT_MERGE", arg=1),
                            ]
                        )
                    else:
                        bytecode += arg.source.emit_bytecodes(function, labels) + [
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
            bytecode += self.target.emit_store_bytecodes(function, labels)

        return bytecode


@Parser.register
class PopElementAssembly(AbstractAssemblyInstruction):
    # POP [<count>]
    NAME = "POP"

    @classmethod
    def consume(cls, parser: "Parser") -> "PopElementAssembly":
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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "POP_TOP", int(self.count.text))
            for _ in range(int(self.count.text))
        ]


@Parser.register
class ReturnAssembly(AbstractAssemblyInstruction):
    # RETURN [<expr>]
    NAME = "RETURN"

    @classmethod
    def consume(cls, parser: "Parser") -> "ReturnAssembly":
        return cls(parser.try_parse_data_source(allow_primitives=True, allow_op=True, include_bracket=False))

    def __init__(self, expr: AbstractSourceExpression | None = None):
        self.expr = expr

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.expr.visit_parts(visitor) if self.expr else None,
            )
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.expr == other.expr

    def __repr__(self):
        return f"RETURN({self.expr})"

    def copy(self) -> "ReturnAssembly":
        return ReturnAssembly(self.expr.copy())

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        expr = self.expr.emit_bytecodes(function, labels) if self.expr else []
        return expr + [
            Instruction(function, -1, "RETURN_VALUE")
        ]


@Parser.register
class YieldAssembly(AbstractAssemblyInstruction):
    # YIELD [*] [<expr>] [-> <taerget>]
    NAME = "YIELD"

    @classmethod
    def consume(cls, parser: "Parser") -> "YieldAssembly":
        is_star = bool(parser.try_consume(SpecialToken("*")))

        expr = parser.try_parse_data_source(allow_primitives=True, allow_op=True, include_bracket=False)

        if parser.try_consume(SpecialToken("-")) and parser.try_consume(SpecialToken(">")):
            target = parser.try_parse_data_source(allow_primitives=True, allow_op=True, include_bracket=False)

            if target is None:
                raise SyntaxError("expected writeable target")

        else:
            target = None

        return cls(expr, is_star, target)

    def __init__(self, expr: AbstractSourceExpression | None = None, is_star: bool = False, target: AbstractSourceExpression | None = None):
        self.expr = expr
        self.is_star = is_star
        self.target = target

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.expr.visit_parts(visitor) if self.expr else None,
                self.target.visit_parts(visitor) if self.target else None,
            )
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.expr == other.expr and self.is_star == other.is_star and self.target == other.target

    def __repr__(self):
        return f"YIELD{'' if not self.is_star else '*'}({self.expr if self.expr else ''}{(', ' if self.expr else '->') + repr(self.target) if self.target else ''})"

    def copy(self) -> "YieldAssembly":
        return YieldAssembly(self.expr.copy() if self.expr else None, self.is_star, self.target.copy() if self.target else None)

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        bytecode = []

        if self.expr:
            bytecode += self.expr.emit_bytecodes(function, labels)

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
            bytecode += self.target.emit_store_bytecodes(function, labels)

        else:
            bytecode += [
                Instruction(function, -1, Opcodes.POP_TOP)
            ]

        print(bytecode)

        return bytecode


@Parser.register
class JumpAssembly(AbstractAssemblyInstruction):
    # JUMP <label name> [(IF <condition access>) | ('(' <expression> | <op expression> ')')]
    NAME = "JUMP"

    @classmethod
    def consume(cls, parser: "Parser") -> "JumpAssembly":
        label_target = parser.consume(IdentifierToken)

        if parser.try_consume(IdentifierToken("IF")):
            condition = parser.try_parse_data_source(allow_primitives=True, include_bracket=False, allow_op=True)

        elif parser.try_consume(SpecialToken("(")):
            parser.save()
            condition = parser.try_parse_data_source(allow_primitives=True, include_bracket=False, allow_op=True)

            if condition is None or not parser.try_consume(SpecialToken(")")):
                parser.rollback()
                condition = OpAssembly.consume(parser)
                parser.consume(SpecialToken(")"))
            else:
                parser.discard_save()

        else:
            condition = None

        return cls(label_target, condition)

    def __init__(self, label_name_token: IdentifierToken | str, condition: AbstractAccessExpression | None = None):
        self.label_name_token = label_name_token if isinstance(label_name_token, IdentifierToken) else IdentifierToken(label_name_token)
        self.condition = condition

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                self.condition.visit_parts(visitor) if self.condition else None,
            )
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.label_name_token == other.label_name_token and self.condition == other.condition

    def __repr__(self):
        return f"JUMP({self.label_name_token.text}{'' if self.condition is None else ', IF '+repr(self.condition)})"

    def copy(self) -> "JumpAssembly":
        return JumpAssembly(self.label_name_token, self.condition.copy() if self.condition else None)

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        if self.condition is None:
            return [Instruction(function, -1, Opcodes.JUMP_ABSOLUTE, JumpToLabel(self.label_name_token.text))]
        return self.condition.emit_bytecodes(function, labels) + [Instruction(function, -1, Opcodes.POP_JUMP_IF_TRUE, JumpToLabel(self.label_name_token.text))]


@Parser.register
class FunctionDefinitionAssembly(AbstractAssemblyInstruction):
    # DEF [<func name>] ['<' ['!'] <bound variables\> '>'] '(' <signature> ')' ['->' <target>] '{' <body> '}'
    NAME = "DEF"
    SKIP_SUB_LABELS = True

    @classmethod
    def consume(cls, parser: "Parser") -> "JumpAssembly":
        func_name = parser.try_consume(IdentifierToken)
        bound_variables: typing.List[typing.Tuple[IdentifierToken, bool]] = []
        args = []

        if parser.try_consume(SpecialToken("<")):
            is_static = bool(parser.try_consume(SpecialToken("!")))

            expr = parser.try_consume(IdentifierToken)

            if expr:
                bound_variables.append((expr, is_static))

            while True:
                if not parser.try_consume(SpecialToken(",")) or not (expr := parser.try_consume(IdentifierToken)):
                    break

                bound_variables.append((expr, is_static))

            parser.consume(SpecialToken(">"))

        parser.consume(SpecialToken("("))

        while parser.try_inspect() != SpecialToken(")"):
            arg = None

            star = parser.try_consume(SpecialToken("*"))
            star_star = parser.try_consume(SpecialToken("*"))
            identifier = parser.try_consume(IdentifierToken)

            if not identifier:
                if star:
                    raise SyntaxError

                break

            if not star:
                if parser.try_consume(SpecialToken("=")):
                    default_value = parser.try_parse_data_source(allow_primitives=True, include_bracket=False, allow_op=True)

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

        if parser.try_consume(SpecialToken("<")):
            raise SyntaxError("Respect ordering (got 'args' before 'captured'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }")

        if parser.try_consume(SpecialToken("-")) and parser.try_consume(SpecialToken(">")):
            target = parser.try_consume_access_token()
        else:
            target = None

        body = parser.parse_body()

        if parser.try_consume(SpecialToken("-")):
            raise SyntaxError("Respect ordering (got 'code' before 'target'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }")

        return cls(func_name, bound_variables, args, body, target)

    def __init__(self, func_name: IdentifierToken | str | None, bound_variables: typing.List[typing.Tuple[IdentifierToken | str, bool] | str], args: typing.List[CallAssembly.IArg], body: CompoundExpression, target: AbstractAccessExpression | None = None):
        self.func_name = func_name if not isinstance(func_name, str) else IdentifierToken(func_name)
        self.bound_variables: typing.List[typing.Tuple[IdentifierToken, bool]] = []  # var if isinstance(var, IdentifierToken) else IdentifierToken(var) for var in bound_variables]

        for element in bound_variables:
            if isinstance(element, str):
                self.bound_variables.append((IdentifierToken(element.removeprefix("!")), element.startswith("!")))
            elif isinstance(element, tuple):
                token, is_static = element

                if isinstance(token, str):
                    self.bound_variables.append((IdentifierToken(token), is_static))
                else:
                    self.bound_variables.append(element)
            else:
                raise ValueError(element)

        self.args = args
        self.body = body
        self.target = target

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (
                [
                    arg.visit_parts(visitor) for arg in self.args
                ],
                self.body.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target else None,
            )
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.func_name == other.func_name and self.bound_variables == other.bound_variables and self.args == other.args and self.body == other.body and self.target == other.target

    def __repr__(self):
        return f"DEF({self.func_name.text}<{repr(self.bound_variables)[1:-1]}>({repr(self.args)[1:-1]}){'-> ' + repr(self.target) if self.target else ''} {{ {self.body} }})"

    def copy(self) -> "FunctionDefinitionAssembly":
        return FunctionDefinitionAssembly(self.func_name, self.bound_variables.copy(), [arg.copy() for arg in self.args], self.body.copy(), self.target.copy() if self.target else None)

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        flags = 0
        bytecode = []

        inner_labels = self.body.collect_label_info()
        label_targets = {}

        target = MutableFunction(lambda: None)
        target.assemble_instructions_from_tree(self.body.emit_bytecodes(target, inner_labels))

        for ins in target.instructions:
            if ins.opcode == Opcodes.BYTECODE_LABEL:
                label_targets[ins.arg_value] = ins.next_instruction
                ins.change_opcode(Opcodes.NOP)

        def resolve_jump_to_label(ins: Instruction):
            if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
                ins.change_arg_value(label_targets[ins.arg_value.name])

        target.instructions[0].apply_visitor(bytecodemanipulation.util.LambdaInstructionWalker(resolve_jump_to_label))

        has_kwarg = False
        for arg in self.args:
            if isinstance(arg, CallAssembly.KwArg):
                has_kwarg = True
                break

        if has_kwarg:
            flags |= 0x02
            raise NotImplementedError("Kwarg defaults")

        if self.bound_variables:
            if any(map(lambda e: e[1], self.bound_variables)):
                raise NotImplementedError("Static variables")

            flags |= 0x08

            bytecode += [
                Instruction(function, -1, "LOAD_CONST", tuple(map(lambda e: e[0], self.bound_variables))),
            ]

        code_object = target.create_code_obj()

        bytecode += [
            Instruction(function, -1, "LOAD_CONST", code_object),
            Instruction(function, -1, "LOAD_CONST", self.func_name.text if self.func_name else "<lambda>"),
            Instruction(function, -1, "MAKE_FUNCTION", arg=flags),
        ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, labels)

        return bytecode


