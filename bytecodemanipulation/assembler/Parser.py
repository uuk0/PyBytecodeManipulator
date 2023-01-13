import copy
import typing
from abc import ABC

from bytecodemanipulation.Opcodes import Opcodes

from bytecodemanipulation.MutableFunction import MutableFunction, Instruction

from bytecodemanipulation.assembler.Lexer import Lexer, SpecialToken, StringLiteralToken
from code_parser.lexers.common import AbstractToken, CommentToken, IdentifierToken, BinaryOperatorToken, IntegerToken, FloatToken, BracketToken
from code_parser.parsers.common import AbstractParser, AbstractExpression, NumericExpression, BracketExpression, BinaryExpression, IdentifierExpression


class CompoundExpression(AbstractExpression):
    def __init__(self, children: typing.List[AbstractExpression] = None):
        self.children = children or []

    def __eq__(self, other):
        return type(self) == type(other) and self.children == other.children

    def __repr__(self):
        return f"Compound({repr(self.children)[1:-1]})"

    def copy(self) -> "CompoundExpression":
        return CompoundExpression([child.copy() for child in self.children])

    def add_child(self, expr: "AbstractExpression"):
        self.children.append(expr)
        return self


class AbstractAssemblyInstruction(AbstractExpression, ABC):
    NAME: str | None = None

    @classmethod
    def consume(cls, parser: "Parser") -> "AbstractAssemblyInstruction":
        raise NotImplementedError

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        raise NotImplementedError


class AbstractSourceExpression(AbstractExpression, ABC):
    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        raise NotImplementedError

    def emit_store_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        raise NotImplementedError


class AbstractAccessExpression(AbstractSourceExpression, ABC):
    PREFIX: str | None = None

    def __init__(self, name_token: IdentifierToken | IntegerToken):
        self.name_token = name_token

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def __repr__(self):
        return f"{self.PREFIX}{self.name_token}"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.name_token)


class GlobalAccessExpression(AbstractAccessExpression):
    PREFIX = "@"

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction(function, -1, "LOAD_GLOBAL", value)
        ]

    def emit_store_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction(function, -1, "STORE_GLOBAL", value)
        ]


class LocalAccessExpression(AbstractAccessExpression):
    PREFIX = "$"

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction(function, -1, "LOAD_FAST", value)
        ]

    def emit_store_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction(function, -1, "STORE_FAST", value)
        ]


class TopOfStackAccessExpression(AbstractAccessExpression):
    PREFIX = "%"

    def __init__(self):
        pass

    def __eq__(self, other):
        return type(self) == type(other)

    def __repr__(self):
        return f"%"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)()

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return []

    def emit_store_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return []


class ConstantAccessExpression(AbstractAccessExpression):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return type(self) == type(other) or self.value == other.value

    def __repr__(self):
        return f"CONSTANT({self.value})"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(copy.deepcopy(self.value))

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "LOAD_CONST", self.value)
        ]

    def emit_store_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        raise SyntaxError("Cannot assign to a constant")


class SubscriptionAccessExpression(AbstractAccessExpression):
    def __init__(self, base_expr: "AbstractAccessExpression", index_expr: AbstractAccessExpression | IntegerToken):
        self.base_expr = base_expr
        self.index_expr = index_expr

    def __eq__(self, other):
        return type(self) == type(other) and self.base_expr == other.base_expr and self.index_expr == self.index_expr

    def __repr__(self):
        return f"{self.base_expr}[{self.index_expr}]"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.base_expr.copy(), self.index_expr.copy())

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return self.base_expr.emit_bytecodes(function) + (self.index_expr.emit_bytecodes(function) if isinstance(self.index_expr, AbstractAccessExpression) else [Instruction(function, -1, "LOAD_CONST", int(self.index_expr.text))]) + [
            Instruction(function, -1, Opcodes.BINARY_SUBSCR)
        ]

    def emit_store_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return self.base_expr.emit_bytecodes(function) + (self.index_expr.emit_bytecodes(function) if isinstance(self.index_expr, AbstractAccessExpression) else [Instruction(function, -1, "LOAD_CONST", int(self.index_expr.text))]) + [
            Instruction(function, -1, Opcodes.STORE_SUBSCR)
        ]


class Parser(AbstractParser):
    INSTRUCTIONS: typing.Dict[str, typing.Type[AbstractAssemblyInstruction]] = {}

    @classmethod
    def register(cls, instr: typing.Type[AbstractAssemblyInstruction]):
        cls.INSTRUCTIONS[instr.NAME] = instr
        return instr

    def __init__(self, tokens_or_str: str | typing.List[AbstractToken]):
        super().__init__(
            tokens_or_str
            if isinstance(tokens_or_str, list)
            else Lexer(tokens_or_str).lex()
        )

    def parse(self) -> AbstractExpression:
        root = CompoundExpression()

        while True:
            self.try_consume(CommentToken)

            if not (instr_token := self.try_consume(IdentifierToken)):
                raise SyntaxError(self.try_inspect())

            if instr_token.text not in self.INSTRUCTIONS:
                raise SyntaxError(instr_token)

            instr = self.INSTRUCTIONS[instr_token.text].consume(self)

            root.add_child(instr)

            if self.is_empty():
                break

            if self.try_consume(SpecialToken(";")):
                continue

            if not (expr := self.try_inspect()):
                continue

            if self[-1].line != expr.line:
                continue

            print(self[-1].line, self[-1], expr.line)

            raise SyntaxError(f"Expected <newline> or ';' after assembly instruction, got {self.try_inspect()}")

        return root

    def try_consume_access_token(self, allow_tos=True, allow_primitives=False) -> AbstractAccessExpression | None:
        start_token = self.try_inspect()

        if start_token is None:
            return

        if allow_primitives:
            if string := self.try_consume(StringLiteralToken):
                return ConstantAccessExpression(string.text)

            if integer := self.try_consume(IntegerToken):
                return ConstantAccessExpression(int(integer.text))

        if not isinstance(start_token, SpecialToken):
            return

        if start_token.text == "@":
            self.consume(SpecialToken("@"))
            expr = GlobalAccessExpression(self.consume([IdentifierToken, IntegerToken]))

        elif start_token.text == "$":
            self.consume(SpecialToken("$"))
            expr = LocalAccessExpression(self.consume([IdentifierToken, IntegerToken]))

        elif start_token.text == "%" and allow_tos:
            self.consume(SpecialToken("%"))
            expr = TopOfStackAccessExpression()

        else:
            return

        if self.try_consume(SpecialToken("[")):
            # Consume either an Integer or a expression
            if not (index := self.try_parse_data_source(allow_primitives=True, allow_tos=allow_tos, include_bracket=False)):
                index = self.consume(IntegerToken)

            self.consume(SpecialToken("]"))
            return SubscriptionAccessExpression(expr, index)

        return expr

    def try_parse_data_source(self, allow_tos=True, allow_primitives=False, include_bracket=True) -> AbstractSourceExpression | None:
        self.save()

        if include_bracket and not (bracket := self.try_consume(SpecialToken("("))):
            self.rollback()
            return

        if access := self.try_consume_access_token(allow_tos=allow_tos, allow_primitives=allow_primitives):
            self.discard_save()
            if include_bracket:
                self.consume(SpecialToken(")"))
            return access

        if allow_primitives:
            if string := self.try_consume(StringLiteralToken):
                return ConstantAccessExpression(string.text)

            if integer := self.try_consume(IntegerToken):
                return ConstantAccessExpression(int(integer.text))

        self.rollback()


@Parser.register
class LoadAssembly(AbstractAssemblyInstruction):
    # LOAD <access>
    NAME = "LOAD"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadAssembly":
        access = parser.try_consume_access_token(allow_tos=False, allow_primitives=True)

        if access is None:
            raise SyntaxError(parser.try_inspect())

        return cls(access)

    def __init__(self, access_token: AbstractAccessExpression):
        self.access_token = access_token

    def __eq__(self, other):
        return type(self) == type(other) and self.access_token == other.access_token

    def __repr__(self):
        return f"LOAD({self.access_token})"

    def copy(self) -> "LoadAssembly":
        return LoadAssembly(self.access_token)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return self.access_token.emit_bytecodes(function)


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

    def __init__(self, access_token: AbstractAccessExpression, source: AbstractSourceExpression | None = None):
        self.access_token = access_token
        self.source = source

    def __eq__(self, other):
        return type(self) == type(other) and self.access_token == other.access_token and self.source == other.source

    def __repr__(self):
        return f"STORE({self.access_token}, {self.source})"

    def copy(self) -> "StoreAssembly":
        return StoreAssembly(self.access_token, self.source.copy() if self.source else None)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return ([] if self.source is None else self.source.emit_bytecodes(function)) + self.access_token.emit_store_bytecodes(function)


@Parser.register
class LoadGlobalAssembly(AbstractAssemblyInstruction):
    # LOAD_GLOBAL <name>
    NAME = "LOAD_GLOBAL"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadGlobalAssembly":
        parser.try_consume(SpecialToken("@"))
        name = parser.consume([IdentifierToken, IntegerToken])

        return cls(name)

    def __init__(self, name_token: IdentifierToken | IntegerToken):
        self.name_token = name_token

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def __repr__(self):
        return f"LOAD_GLOBAL({self.name_token})"

    def copy(self) -> "LoadGlobalAssembly":
        return LoadGlobalAssembly(self.name_token)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction(function, -1, "LOAD_GLOBAL", value)
        ]


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

    def __init__(self, name_token: IdentifierToken, source: AbstractSourceExpression | None = None):
        self.name_token = name_token
        self.source = source

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token and self.source == other.source

    def __repr__(self):
        return f"STORE_GLOBAL({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "StoreGlobalAssembly":
        return StoreGlobalAssembly(self.name, self.source.copy() if self.source else None)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return ([] if self.source is None else self.source.emit_bytecodes(function)) + [
            Instruction(function, -1, "STORE_GLOBAL", value)
        ]


@Parser.register
class LoadFastAssembly(AbstractAssemblyInstruction):
    # LOAD_FAST <name>
    NAME = "LOAD_FAST"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadFastAssembly":
        parser.try_consume(SpecialToken("$"))
        name = parser.consume([IdentifierToken, IntegerToken])

        return cls(name)

    def __init__(self, name_token: IdentifierToken | IntegerToken):
        self.name_token = name_token

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def __repr__(self):
        return f"LOAD_GLOBAL({self.name_token})"

    def copy(self) -> "LoadFastAssembly":
        return LoadFastAssembly(self.name_token)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction(function, -1, "LOAD_FAST", value)
        ]


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

    def __init__(self, name_token: IdentifierToken, source: AbstractSourceExpression | None = None):
        self.name_token = name_token
        self.source = source

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token and self.source == other.source

    def __repr__(self):
        return f"STORE_FAST({self.name_token}, source={self.source or 'TOS'})"

    def copy(self) -> "StoreFastAssembly":
        return StoreFastAssembly(self.name, self.source.copy() if self.source else None)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return ([] if self.source is None else self.source.emit_bytecodes(function)) + [
            Instruction(function, -1, "STORE_FAST", value)
        ]


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
        return f"POP(#{self.count})"

    def copy(self) -> "PopElementAssembly":
        return PopElementAssembly(self.count)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "POP_TOP", self.name_token.text)
            for _ in range(int(self.count.text))
        ]
