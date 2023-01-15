import copy
import typing
from abc import ABC

from bytecodemanipulation.Opcodes import Opcodes

from bytecodemanipulation.MutableFunction import MutableFunction, Instruction

from bytecodemanipulation.assembler.Lexer import Lexer, SpecialToken, StringLiteralToken

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


class JumpToLabel:
    def __init__(self, name: str):
        self.name = name


class IAssemblyStructureVisitable(ABC):
    def visit_parts(
        self,
        visitor: typing.Callable[["IAssemblyStructureVisitable", tuple], typing.Any],
    ):
        raise NotImplementedError

    def visit_assembly_instructions(
        self,
        visitor: typing.Callable[["IAssemblyStructureVisitable", tuple], typing.Any],
    ):
        raise NotImplementedError

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        max_stack_size = 0
        effect = 0

        if children is None:
            raise RuntimeError(self)

        for x in children:
            if x is None: continue

            eff, m = x
            max_stack_size = max(max_stack_size, m)
            effect += eff

        return effect, max(max_stack_size, effect, 0)


class CompoundExpression(AbstractExpression, IAssemblyStructureVisitable):
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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return sum((child.emit_bytecodes(function, labels) for child in self.children), [])

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self, tuple([child.visit_parts(visitor) for child in self.children])
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            tuple(
                [child.visit_assembly_instructions(visitor) for child in self.children]
            ),
        )

    def collect_label_info(self) -> typing.Set[str]:
        return set(self.visit_assembly_instructions(lambda asm, prev: sum(prev, tuple()) + ((asm.name_token.text,) if isinstance(asm, LabelAssembly) else tuple())))

    def create_bytecode(self, target: MutableFunction, labels: typing.Set[str]):
        return self.emit_bytecodes(target, labels)

    def get_stack_effect_stats(self) -> typing.Tuple[int, int]:
        def visit(element: IAssemblyStructureVisitable, children) -> typing.Tuple[int, int]:
            return element._get_stack_effect_stats(children)

        return self.visit_parts(visit)


class AbstractAssemblyInstruction(AbstractExpression, IAssemblyStructureVisitable, ABC):
    NAME: str | None = None

    @classmethod
    def consume(cls, parser: "Parser") -> "AbstractAssemblyInstruction":
        raise NotImplementedError

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        raise NotImplementedError

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ) -> tuple:
        return visitor(self, tuple())

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, tuple())


class AbstractSourceExpression(AbstractExpression, IAssemblyStructureVisitable, ABC):
    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        raise NotImplementedError

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        raise NotImplementedError

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, tuple())

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        pass


class AbstractAccessExpression(AbstractSourceExpression, ABC):
    PREFIX: str | None = None

    def __init__(self, name_token: IdentifierToken | IntegerToken | str):
        self.name_token = (
            name_token
            if not isinstance(name_token, str)
            else IdentifierToken(name_token)
        )

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def __repr__(self):
        return f"{self.PREFIX}{self.name_token.text}"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.name_token)

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        raise NotImplementedError


class GlobalAccessExpression(AbstractAccessExpression):
    PREFIX = "@"

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_GLOBAL", value)]

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "STORE_GLOBAL", value)]

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return 1, 1


class LocalAccessExpression(AbstractAccessExpression):
    PREFIX = "$"

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "LOAD_FAST", value)]

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [Instruction(function, -1, "STORE_FAST", value)]

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return 1, 1


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

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return []

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        return []

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return 0, 0


class ConstantAccessExpression(AbstractAccessExpression):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return type(self) == type(other) or self.value == other.value

    def __repr__(self):
        return f"CONSTANT({self.value})"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(copy.deepcopy(self.value))

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return [Instruction(function, -1, "LOAD_CONST", self.value)]

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        raise SyntaxError("Cannot assign to a constant")

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return 1, 1


class SubscriptionAccessExpression(AbstractAccessExpression):
    def __init__(
        self,
        base_expr: "AbstractAccessExpression",
        index_expr: AbstractAccessExpression | IntegerToken,
    ):
        self.base_expr = base_expr
        self.index_expr = index_expr

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.base_expr == other.base_expr
            and self.index_expr == self.index_expr
        )

    def __repr__(self):
        return f"{self.base_expr}[{self.index_expr}]"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(self.base_expr.copy(), self.index_expr.copy())

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return (
            self.base_expr.emit_bytecodes(function, labels)
            + (
                self.index_expr.emit_bytecodes(function, labels)
                if isinstance(self.index_expr, AbstractAccessExpression)
                else [
                    Instruction(function, -1, "LOAD_CONST", int(self.index_expr.text))
                ]
            )
            + [Instruction(function, -1, Opcodes.BINARY_SUBSCR)]
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        return (
            self.base_expr.emit_bytecodes(function, labels)
            + (
                self.index_expr.emit_bytecodes(function, labels)
                if isinstance(self.index_expr, AbstractAccessExpression)
                else [
                    Instruction(function, -1, "LOAD_CONST", int(self.index_expr.text))
                ]
            )
            + [Instruction(function, -1, Opcodes.STORE_SUBSCR)]
        )

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(
            self,
            (self.base_expr.visit_parts(visitor), self.index_expr.visit_parts(visitor)),
        )

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return -1, 0


class AttributeAccessExpression(AbstractAccessExpression):
    def __init__(
        self, root: AbstractAccessExpression, name_token: IdentifierToken | str
    ):
        self.root = root
        self.name_token = (
            name_token
            if isinstance(name_token, IdentifierToken)
            else IdentifierToken(name_token)
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.root == other.root
            and self.name_token == other.name_token
        )

    def __repr__(self):
        return f"{self.root}.{self.name_token.text}"

    def copy(self) -> "AttributeAccessExpression":
        return AttributeAccessExpression(self.root.copy(), self.name_token)

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, labels) + [
            Instruction(function, -1, "LOAD_ATTR", self.name_token.text)
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, labels: typing.Set[str]
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, labels) + [
            Instruction(function, -1, "STORE_ATTR", self.name_token.text)
        ]

    def visit_parts(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.root.visit_parts(visitor),))

    def _get_stack_effect_stats(self, children: typing.Iterable[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return -1, 0


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

    def parse(self) -> CompoundExpression:
        return self.parse_while_predicate(lambda: not self.is_empty())

    def parse_body(self) -> CompoundExpression:
        self.consume(SpecialToken("{"))
        return self.parse_while_predicate(
            lambda: not self.try_consume(SpecialToken("}")),
            eof_error="Expected '}', got EOF",
        )

    def parse_while_predicate(
        self, predicate: typing.Callable[[], bool], eof_error: str = None
    ) -> CompoundExpression:
        root = CompoundExpression()

        while predicate():
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

            raise SyntaxError(
                f"Expected <newline> or ';' after assembly instruction, got {self.try_inspect()}"
            )

        if eof_error and not predicate():
            raise SystemError(eof_error)

        return root

    def try_consume_access_token(
        self, allow_tos=True, allow_primitives=False, allow_op=True
    ) -> AbstractAccessExpression | None:
        start_token = self.try_inspect()

        if start_token is None:
            return

        if allow_primitives:
            if string := self.try_consume(StringLiteralToken):
                return ConstantAccessExpression(string.text)

            if integer := self.try_consume(IntegerToken):
                return ConstantAccessExpression(int(integer.text))

        if not isinstance(start_token, (SpecialToken, IdentifierToken)):
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

        elif start_token.text == "OP" and allow_op and "OP" in self.INSTRUCTIONS:
            self.consume(start_token)
            self.consume(SpecialToken("("))
            expr = self.INSTRUCTIONS["OP"].consume(self)
            self.consume(SpecialToken(")"))

        else:
            return

        while self.try_consume(SpecialToken(".")):
            expr = AttributeAccessExpression(expr, self.consume(IdentifierToken))

        if self.try_consume(SpecialToken("[")):
            # Consume either an Integer or a expression
            if not (
                index := self.try_parse_data_source(
                    allow_primitives=True,
                    allow_tos=allow_tos,
                    include_bracket=False,
                    allow_op=allow_op,
                )
            ):
                raise SyntaxError(self.try_inspect())

            while self.try_consume(SpecialToken(".")):
                expr = AttributeAccessExpression(expr, self.consume(IdentifierToken))

            self.consume(SpecialToken("]"))
            return SubscriptionAccessExpression(expr, index)

        return expr

    def try_parse_data_source(
        self,
        allow_tos=True,
        allow_primitives=False,
        include_bracket=True,
        allow_op=True,
    ) -> AbstractSourceExpression | None:
        self.save()

        if include_bracket and not self.try_consume(SpecialToken("(")):
            self.rollback()
            return

        if access := self.try_consume_access_token(
            allow_tos=allow_tos, allow_primitives=allow_primitives, allow_op=allow_op
        ):
            self.discard_save()
            if include_bracket:
                self.consume(SpecialToken(")"))
            return access

        if allow_primitives:
            if string := self.try_consume(StringLiteralToken):
                return ConstantAccessExpression(string.text)

            if integer := self.try_consume(IntegerToken):
                return ConstantAccessExpression(int(integer.text))

        print(self.try_inspect())

        self.rollback()

    @staticmethod
    def _get_stack_effect_stats(children: typing.Tuple[typing.Tuple[int, int]]) -> typing.Tuple[int, int]:
        return -1, 0


@Parser.register
class LabelAssembly(AbstractAssemblyInstruction):
    # LABEL <name>
    NAME = "LABEL"

    @classmethod
    def consume(cls, parser: "Parser") -> "AbstractAssemblyInstruction":
        pass

    def __init__(self, name_token: IdentifierToken | str):
        self.name_token = name_token if isinstance(name_token, IdentifierToken) else IdentifierToken(name_token)

    def emit_bytecodes(self, function: MutableFunction, labels: typing.Set[str]) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, Opcodes.BYTECODE_LABEL, self.name_token.text)
        ]

    def copy(self) -> "LabelAssembly":
        return type(self)(self.name_token)
