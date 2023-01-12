import typing
from abc import ABC

from bytecodemanipulation.Opcodes import Opcodes

from bytecodemanipulation.MutableFunction import MutableFunction, Instruction

from bytecodemanipulation.assembler.Lexer import Lexer, SpecialToken
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


class AbstractAccessExpression(AbstractExpression, ABC):
    PREFIX: str | None = None

    def __init__(self, name_token: IdentifierToken):
        self.name_token = name_token

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def __repr__(self):
        return f"{self.PREFIX}{self.name_token}"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.name_token)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        raise NotImplementedError


class GlobalAccessExpression(AbstractAccessExpression):
    PREFIX = "@"

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "LOAD_GLOBAL", self.name_token.text)
        ]


class LocalAccessExpression(AbstractAccessExpression):
    PREFIX = "$"

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "LOAD_FAST", self.name_token.text)
        ]


class SubscriptionAccessExpression(AbstractAccessExpression):
    def __init__(self, base_expr: "AbstractAccessExpression", index_expr: AbstractExpression | IntegerToken):
        self.base_expr = base_expr
        self.index_expr = index_expr

    def __eq__(self, other):
        return type(self) == type(other) and self.base_expr == other.base_expr and self.index_expr == self.index_expr

    def __repr__(self):
        return f"{self.base_expr}[{self.index_expr}]"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.base_expr.copy(), self.index_expr.copy())

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return self.base_expr.emit_bytecodes(function) + self.index_expr.emit_bytecodes(function) + [
            Instruction(function, -1, Opcodes.BINARY_SUBSCR)
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

    def try_consume_access_token(self) -> AbstractAccessExpression | None:
        start_token = self.try_inspect()

        if start_token is None:
            return

        if not isinstance(start_token, SpecialToken):
            return

        if start_token.text == "@":
            self.consume(SpecialToken("@"))
            expr = GlobalAccessExpression(self.consume(IdentifierToken))

        elif start_token.text == "$":
            self.consume(SpecialToken("$"))
            expr = LocalAccessExpression(self.consume(IdentifierToken))

        else:
            return

        if self.try_consume(SpecialToken("[")):
            index = self.consume(IntegerToken)  # todo: consume expression
            self.consume(SpecialToken("]"))
            return SubscriptionAccessExpression(expr, index)

        return expr


@Parser.register
class LoadAssembly(AbstractAssemblyInstruction):
    # LOAD <access>
    NAME = "LOAD"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadAssembly":
        access = parser.try_consume_access_token()

        if access is None:
            raise SyntaxError

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
class LoadGlobalAssembly(AbstractAssemblyInstruction):
    # LOAD_GLOBAL <name>
    NAME = "LOAD_GLOBAL"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadGlobalAssembly":
        parser.try_consume(SpecialToken("@"))
        name = parser.consume(IdentifierToken)

        return cls(name)

    def __init__(self, name_token: IdentifierToken):
        self.name_token = name_token

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def __repr__(self):
        return f"LOAD_GLOBAL({self.name_token})"

    def copy(self) -> "LoadGlobalAssembly":
        return LoadGlobalAssembly(self.name_token)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "LOAD_GLOBAL", self.name_token.text)
        ]


@Parser.register
class LoadFastAssembly(AbstractAssemblyInstruction):
    # LOAD_FAST <name>
    NAME = "LOAD_FAST"

    @classmethod
    def consume(cls, parser: "Parser") -> "LoadFastAssembly":
        parser.try_consume(SpecialToken("@"))
        name = parser.consume(IdentifierToken)

        return cls(name)

    def __init__(self, name_token: IdentifierToken):
        self.name_token = name_token

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.access_token

    def __repr__(self):
        return f"LOAD_GLOBAL({self.name_token})"

    def copy(self) -> "LoadFastAssembly":
        return LoadFastAssembly(self.name_token)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, "LOAD_FAST", self.name_token.text)
        ]


@Parser.register
class PopElementAssembly(AbstractAssemblyInstruction):
    # POP [<index>]
    NAME = "POP"

    @classmethod
    def consume(cls, parser: "Parser") -> "PopElementAssembly":
        index = parser.try_consume(IntegerToken)
        return cls(index if index is not None else IntegerToken("0"))

    def __init__(self, index: IntegerToken):
        self.index = index

    def __eq__(self, other):
        return type(self) == type(other) and self.index == other.index

    def __repr__(self):
        return f"POP({self.index})"

    def copy(self) -> "PopElementAssembly":
        return PopElementAssembly(self.index)

    def emit_bytecodes(self, function: MutableFunction) -> typing.List[Instruction]:
        assert self.index.text == "0", "currently not supported!"

        return [
            Instruction(function, -1, "POP_TOP", self.name_token.text)
        ]
