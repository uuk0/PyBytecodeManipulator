import copy
import typing
import warnings
from abc import ABC

from bytecodemanipulation.Opcodes import Opcodes

from bytecodemanipulation.MutableFunction import MutableFunction, Instruction

from bytecodemanipulation.assembler.Lexer import (
    Lexer,
    SpecialToken,
    StringLiteralToken,
    PythonCodeToken,
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


def create_instruction(token: AbstractToken, *args, **kwargs) -> Instruction:
    instr = Instruction(*args, **kwargs)
    instr.source_location = token.line, token.column, token.span
    return instr


Instruction.create_with_token = create_instruction


class ParsingScope:
    def __init__(self):
        self.labels: typing.Set[str] = set()
        self.global_scope = {}
        self.scope_path: typing.List[str] = []
        self._name_counter = 1

    def scope_name_generator(self, suffix="") -> str:
        name = f"%INTERNAL:{self._name_counter}"
        self._name_counter += 1

        if suffix:
            name += "/" + suffix

        return name

    def lookup_name_in_scope(self, name: str):
        for i in range(len(self.scope_path), -1, -1):
            path = self.scope_path[:i]

            scope = self.global_scope
            for e in path:
                scope = scope.setdefault(e, {})

            if name in scope:
                return scope[name]

    def lookup_namespace(self, name: typing.List[str]):
        scope = self.global_scope

        for e in name:
            scope = scope.setdefault(e, {})

        return scope


    def exists_label(self, name: str) -> bool:
        return name in self.labels

    def copy(
        self,
        sub_scope_name: str = None,
        copy_labels=False,
        keep_scope_name_generator: bool = None,
    ):
        instance = ParsingScope()
        if copy_labels:
            instance.labels = self.labels
        instance.global_scope = self.global_scope
        instance.scope_path = self.scope_path.copy()

        if sub_scope_name is not None:
            instance.scope_path.append(sub_scope_name)
        elif keep_scope_name_generator:
            instance.scope_name_generator = self.scope_name_generator

        return instance

    def insert_into_scope(
        self, name: typing.List[str], data: typing.Any, override_existing=False
    ):
        if not name:
            raise ValueError("'name' must have at least one element!")

        scope = self.global_scope

        for e in (self.scope_path + name)[:-1]:
            scope = scope.setdefault(e, {})

        if name[-1] in scope and not override_existing:
            raise ValueError(f"name '{name[-1]}' does already exists in the scope!")

        scope[name[-1]] = data


class JumpToLabel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"-> Label('{self.name}')"


class IAssemblyStructureVisitable(ABC):
    def visit_parts(
        self,
        visitor: typing.Callable[
            ["IAssemblyStructureVisitable", tuple, list], typing.Any
        ],
        parents: list,
    ):
        raise NotImplementedError

    def visit_assembly_instructions(
        self,
        visitor: typing.Callable[["IAssemblyStructureVisitable", tuple], typing.Any],
    ):
        raise NotImplementedError


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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return sum(
            (child.emit_bytecodes(function, scope) for child in self.children), []
        )

    def fill_scope_complete(self, scope: ParsingScope):
        def visitor(
            expression: AbstractExpression,
            _,
            parents: typing.List[AbstractAccessExpression],
        ):
            if (
                hasattr(expression, "fill_scope")
                and type(expression).fill_scope
                != AbstractAssemblyInstruction.fill_scope
            ):
                scope.scope_path = sum(
                    [
                        [expr.name.text]
                        for expr in parents
                        if isinstance(expr, NamespaceAssembly)
                    ],
                    [],
                )
                expression.fill_scope(scope)

        self.visit_parts(visitor, [])
        return scope

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
            tuple(
                [
                    child.visit_parts(visitor, parents + [self])
                    for child in self.children
                ]
            ),
            parents,
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
        return self.get_labels()

    def get_labels(self) -> typing.Set[str]:
        result = set()

        for instr in self.children:
            result.update(instr.get_labels())

        return result

    def create_bytecode(self, target: MutableFunction, scope: ParsingScope):
        return self.emit_bytecodes(target, scope)


class AbstractAssemblyInstruction(AbstractExpression, IAssemblyStructureVisitable, ABC):
    NAME: str | None = None

    @classmethod
    def consume(cls, parser: "Parser") -> "AbstractAssemblyInstruction":
        raise NotImplementedError

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise NotImplementedError

    def fill_scope_complete(self, scope: ParsingScope):
        self.visit_parts(
            lambda e, _: e.fill_scope(scope) if hasattr(e, "fill_scope") else None
        )
        return scope

    def fill_scope(self, scope: ParsingScope):
        pass

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(self, tuple(), parents)

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, tuple())

    def get_labels(self) -> typing.Set[str]:
        return set()


class AbstractSourceExpression(AbstractExpression, IAssemblyStructureVisitable, ABC):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise NotImplementedError

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise NotImplementedError

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(self, tuple(), parents)

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


class GlobalAccessExpression(AbstractAccessExpression):
    PREFIX = "@"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "LOAD_GLOBAL", value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "STORE_GLOBAL", value
            )
        ]


class GlobalStaticAccessExpression(AbstractAccessExpression):
    PREFIX = "@!"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        key = self.name_token.text
        value = function.target.__globals__.get(key)
        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "LOAD_CONST", value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError("Cannot assign to a constant global")


class LocalAccessExpression(AbstractAccessExpression):
    PREFIX = "$"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "LOAD_FAST", value, _decode_next=False
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "STORE_FAST", value
            )
        ]


class DerefAccessExpression(AbstractAccessExpression):
    PREFIX = "§"

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "LOAD_DEREF", value, _decode_next=False
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self.name_token.text

        if value.isdigit():
            value = int(value)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "STORE_DEREF", value
            )
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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return []

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction(function, -1, "LOAD_CONST", self.value)]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise SyntaxError("Cannot assign to a constant")


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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            self.base_expr.emit_bytecodes(function, scope)
            + (
                self.index_expr.emit_bytecodes(function, scope)
                if isinstance(self.index_expr, AbstractAccessExpression)
                else [
                    Instruction.create_with_token(
                        self.index_expr,
                        function,
                        -1,
                        "LOAD_CONST",
                        int(self.index_expr.text),
                    )
                ]
            )
            + [
                Instruction.create_with_token(
                    self.name_token, function, -1, Opcodes.BINARY_SUBSCR
                )
            ]
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            self.base_expr.emit_bytecodes(function, scope)
            + (
                self.index_expr.emit_bytecodes(function, scope)
                if isinstance(self.index_expr, AbstractAccessExpression)
                else [
                    Instruction.create_with_token(
                        self.index_expr,
                        function,
                        -1,
                        "LOAD_CONST",
                        int(self.index_expr.text),
                    )
                ]
            )
            + [
                Instruction.create_with_token(
                    self.name_token, function, -1, Opcodes.STORE_SUBSCR
                )
            ]
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
            (self.base_expr.visit_parts(visitor), self.index_expr.visit_parts(visitor)),
        )


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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, scope) + [
            Instruction.create_with_token(
                self.name_token, function, -1, "LOAD_ATTR", self.name_token.text
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, scope) + [
            Instruction.create_with_token(
                self.name_token, function, -1, "STORE_ATTR", self.name_token.text
            )
        ]

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(self, (self.root.visit_parts(visitor),))


class DynamicAttributeAccessExpression(AbstractAccessExpression):
    def __init__(
        self, root: AbstractAccessExpression, name_expr: AbstractSourceExpression
    ):
        self.root = root
        self.name_expr = name_expr

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.root == other.root
            and self.name_expr == other.name_expr
        )

    def __repr__(self):
        return f"{self.root}.{self.name_expr}"

    def copy(self) -> "DynamicAttributeAccessExpression":
        return DynamicAttributeAccessExpression(self.root.copy(), self.name_expr.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [Instruction(function, -1, Opcodes.LOAD_CONST, getattr)]
            + self.root.emit_bytecodes(function, scope)
            + self.name_expr.emit_bytecodes(function, scope)
            + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)]
        )

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return (
            [Instruction(function, -1, Opcodes.LOAD_CONST, setattr)]
            + self.root.emit_bytecodes(function, scope)
            + self.name_expr.emit_bytecodes(function, scope)
            + [
                Instruction(function, -1, Opcodes.ROT_THREE),
                Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2),
            ]
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
            self, (self.root.visit_parts(visitor, parents + [self]),), parents
        )


class MacroAccessExpression(AbstractAccessExpression):
    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def __init__(self, name: typing.List[IdentifierToken]):
        self.name = name

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __repr__(self):
        return f"MACRO-LINK({':'.join(map(lambda e: e.text, self.name))})"

    def copy(self) -> "MacroAccessExpression":
        return type(self)(self.name.copy())


class Parser(AbstractParser):
    INSTRUCTIONS: typing.Dict[str, typing.Type[AbstractAssemblyInstruction]] = {}

    T = typing.TypeVar(
        "T", typing.Type[AbstractAssemblyInstruction], AbstractAssemblyInstruction
    )

    @classmethod
    def register(cls, instr: T) -> T:
        cls.INSTRUCTIONS[instr.NAME] = instr
        return instr

    def __init__(self, tokens_or_str: str | typing.List[AbstractToken], scope: ParsingScope = None):
        super().__init__(
            tokens_or_str
            if isinstance(tokens_or_str, list)
            else Lexer(tokens_or_str).lex()
        )
        self.scope = scope or ParsingScope()

    def parse(self) -> CompoundExpression:
        return self.parse_while_predicate(lambda: not self.is_empty())

    def parse_body(self, namespace_part: str = None) -> CompoundExpression:
        if namespace_part is not None:
            self.scope.scope_path.append(namespace_part)

        self.consume(SpecialToken("{"))
        body = self.parse_while_predicate(
            lambda: not self.try_consume(SpecialToken("}")),
            eof_error="Expected '}', got EOF",
        )

        if namespace_part:
            if self.scope.scope_path.pop() != namespace_part:
                raise RuntimeError

        return body

    def parse_while_predicate(
        self, predicate: typing.Callable[[], bool], eof_error: str = None
    ) -> CompoundExpression:
        root = CompoundExpression()

        while predicate():
            if self.try_consume(CommentToken):
                continue

            if not (instr_token := self.try_consume(IdentifierToken)):
                raise SyntaxError(f"expected Identifier, got {self.try_inspect()}")

            if instr_token.text not in self.INSTRUCTIONS:
                if not (instr := self.try_parse_custom_assembly(instr_token)):
                    raise SyntaxError(
                        f"expected <assembly instruction name> or <assembly macro name>, got '{instr_token.text}'"
                    )
            else:
                instr = self.INSTRUCTIONS[instr_token.text].consume(self)

            root.add_child(instr)

            instr.fill_scope(self.scope)

            if self.is_empty():
                break

            if self.try_consume(SpecialToken(";")):
                continue

            if not (expr := self.try_inspect()):
                continue

            if self[-1].line != expr.line:
                continue

            if not predicate():
                if eof_error:
                    print(self.try_inspect())
                    print(repr(root))
                    raise SyntaxError(eof_error)

                break

            print(self[-1].line, self[-1], expr.line)

            raise SyntaxError(
                f"Expected <newline> or ';' after assembly instruction, got {self.try_inspect()}"
            )

        return root

    def try_parse_custom_assembly(self, base_token: IdentifierToken):
        self.cursor -= 1
        self.save()
        self.cursor += 1

        name = [base_token.text]

        while self.try_consume(SpecialToken(":")):
            name.append(self.consume(IdentifierToken).text)

        target = self.scope.lookup_namespace(name)

        if isinstance(target, MacroAssembly.MacroOverloadPage):
            for macro in typing.cast(MacroAssembly.MacroOverloadPage, target).assemblies:
                if macro.allow_assembly_instr:
                    self.rollback()
                    return MacroAssembly.consume_call(self)

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

            if self.try_consume(SpecialToken("!")):
                expr = GlobalStaticAccessExpression(
                    self.consume([IdentifierToken, IntegerToken])
                )
            else:
                expr = GlobalAccessExpression(
                    self.consume([IdentifierToken, IntegerToken])
                )

        elif start_token.text == "$":
            self.consume(SpecialToken("$"))
            expr = LocalAccessExpression(self.consume([IdentifierToken, IntegerToken]))

        elif start_token.text == "§":
            self.consume(SpecialToken("§"))
            expr = DerefAccessExpression(self.consume([IdentifierToken, IntegerToken]))

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
            if self.try_consume(SpecialToken("(")):
                source = self.try_parse_data_source(
                    allow_tos=True, allow_primitives=True, include_bracket=False
                )

                if source is None:
                    raise SyntaxError("expected expression")

                expr = DynamicAttributeAccessExpression(expr, source)
                self.consume(SpecialToken(")"))
            else:
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


@Parser.register
class LabelAssembly(AbstractAssemblyInstruction):
    # LABEL <name>
    NAME = "LABEL"

    @classmethod
    def consume(cls, parser: "Parser") -> "AbstractAssemblyInstruction":
        return cls(parser.consume(IdentifierToken))

    def __init__(self, name_token: IdentifierToken | str):
        self.name_token = (
            name_token
            if isinstance(name_token, IdentifierToken)
            else IdentifierToken(name_token)
        )

    def __repr__(self):
        return f"LABEL({self.name_token.text})"

    def __eq__(self, other):
        return type(self) == type(other) and self.name_token == other.name_token

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction(function, -1, Opcodes.BYTECODE_LABEL, self.name_token.text)]

    def copy(self) -> "LabelAssembly":
        return type(self)(self.name_token)

    def get_labels(self) -> typing.Set[str]:
        return {self.name_token.text}


@Parser.register
class PythonCodeAssembly(AbstractAssemblyInstruction):
    # PYTHON '{' <code> '}'
    NAME = "PYTHON"

    @classmethod
    def consume(cls, parser: "Parser") -> "PythonCodeAssembly":
        return cls(parser.consume(PythonCodeToken))

    def __init__(self, code: PythonCodeToken | str):
        self.code = code if isinstance(code, PythonCodeToken) else PythonCodeToken(code)

    def __repr__(self):
        return f"PYTHON({repr(self.code)})"

    def __eq__(self, other):
        return type(self) == type(other) and self.code == other.code

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        inner_code = "\n    ".join(self.code.text.split("\n"))
        code = f"def target():\n    {inner_code}"

        ctx = {}
        exec(code, ctx)

        mutable = MutableFunction(ctx["target"])

        instructions = []

        for instr in mutable.instructions:
            instr.update_owner(
                function, offset=-1, update_following=False, force_change_arg_index=True
            )
            instructions.append(instr)

        return instructions

    def copy(self) -> "PythonCodeAssembly":
        return type(self)(self.code)


@Parser.register
class NamespaceAssembly(AbstractAssemblyInstruction):
    # 'NAMESPACE' <name> '{' <code> '}'
    NAME = "NAMESPACE"

    @classmethod
    def consume(cls, parser: "Parser") -> "NamespaceAssembly":
        name = parser.consume(IdentifierToken)
        assembly = parser.parse_body(name.text)

        return cls(
            name,
            assembly,
        )

    def __init__(self, name: IdentifierToken, assembly: CompoundExpression):
        self.name = name
        self.assembly = assembly

    def __repr__(self):
        return f"NAMESPACE::'{self.name.text}'({repr(self.assembly)})"

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.name == other.name
            and self.assembly == other.assembly
        )

    def copy(self):
        return type(self)(self.name, self.assembly.copy())

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.assembly.emit_bytecodes(
            function, scope.copy(sub_scope_name=self.name.text)
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
                self.assembly.visit_parts(
                    visitor,
                    parents + [self],
                ),
            ),
            parents,
        )


@Parser.register
class MacroAssembly(AbstractAssemblyInstruction):
    # 'MACRO' ['ASSEMBLY'] [{<namespace> ':'}] <name> ['(' <param> \[{',' <param>}] ')'] '{' <assembly code> '}', where param is ['!'] \<name> [<data type>]
    NAME = "MACRO"

    class MacroArg:
        def __init__(self, name: IdentifierToken, is_static=False):
            self.name = name
            self.is_static = is_static
            self.index = -1

        def copy(self):
            return type(self)(self.name, self.is_static)

    class MacroOverloadPage:
        def __init__(self, name: typing.List[str]):
            self.name = name
            self.assemblies: typing.List[MacroAssembly] = []

        def lookup(self, args: typing.List[AbstractAccessExpression]) -> "MacroAssembly":
            for macro in self.assemblies:
                if len(macro.args) == len(args):
                    return macro

            raise NameError(f"Could not find overloaded variant of {':'.join(self.name)} with arg count {len(args)}!")

        def add_definition(self, macro: "MacroAssembly"):
            # todo: do a safety check!
            self.assemblies.append(macro)

    @classmethod
    def consume(cls, parser: "Parser") -> "MacroAssembly":
        allow_assembly_instr = bool(parser.try_consume(IdentifierToken("ASSEMBLY")))

        name = [parser.consume(IdentifierToken)]

        while parser.try_consume(SpecialToken(":")):
            name.append(parser.consume(IdentifierToken))

        args = []
        if parser.try_consume(SpecialToken("(")):
            i = 0

            while not parser.try_consume(SpecialToken(")")):
                is_static = bool(parser.try_consume(SpecialToken("!")))
                parameter_name = parser.consume(IdentifierToken)

                arg = MacroAssembly.MacroArg(parameter_name, is_static)
                arg.index = i
                i += 1
                args.append(arg)

                if not parser.try_consume(SpecialToken(",")):
                    parser.consume(SpecialToken(")"))
                    break

        body = parser.parse_body()

        return cls(name, args, body, allow_assembly_instr)

    @classmethod
    def consume_call(cls, parser: Parser) -> AbstractAssemblyInstruction:
        raise RuntimeError

    def __init__(
        self,
        name: typing.List[IdentifierToken],
        args: typing.List[MacroArg],
        body: CompoundExpression,
        allow_assembly_instr=False,
    ):
        self.name = name
        self.args = args
        self.body = body
        self.allow_assembly_instr = allow_assembly_instr

    def __repr__(self):
        return f"MACRO:{'ASSEMBLY' if self.allow_assembly_instr else ''}:'{':'.join(map(lambda e: e.text, self.name))}'({', '.join(map(repr, self.args))}) {{{repr(self.body)}}}"

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.name == other.name
            and self.args == other.args
            and self.body == other.body
            and self.allow_assembly_instr == other.allow_assembly_instr
        )

    def copy(self) -> "MacroAssembly":
        return type(self)(
            self.name.copy(),
            [arg.copy() for arg in self.args],
            self.body.copy(),
            self.allow_assembly_instr,
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return []

    def emit_call_bytecode(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        args: typing.List[AbstractAccessExpression],
    ) -> typing.List[Instruction]:
        if len(args) != len(self.args):
            raise RuntimeError("Argument count must be equal!")

        bytecode = []

        inner_bytecode = self.body.emit_bytecodes(function, scope)

        arg_names: typing.List[str | None] = []
        arg_decl_lookup: typing.Dict[str, MacroAssembly.MacroArg] = {}
        for i, (arg_decl, arg_code) in enumerate(zip(self.args, args)):
            arg_decl_lookup[arg_decl.name.text] = arg_decl
            if arg_decl.is_static:
                arg_names.append(var_name := scope.scope_name_generator(f"arg_{i}"))
                bytecode += arg_code.emit_bytecodes(function, scope)
                bytecode.append(
                    Instruction(
                        function,
                        -1,
                        Opcodes.STORE_FAST,
                        var_name,
                        _decode_next=False,
                    )
                )
            else:
                arg_names.append(None)

        local_prefix = scope.scope_name_generator("macro_local")

        for instr in inner_bytecode:
            bytecode.append(instr)

            if instr.opcode in (Opcodes.LOAD_DEREF, Opcodes.MACRO_PARAMETER_EXPANSION):
                if instr.arg_value not in arg_decl_lookup:
                    continue

                arg_decl = arg_decl_lookup[instr.arg_value]

                if arg_decl.is_static:
                    instr.change_opcode(Opcodes.LOAD_FAST, arg_names[arg_decl.index])

                else:
                    instr.change_opcode(Opcodes.NOP)
                    instructions = args[arg_decl.index].emit_bytecodes(function, scope)
                    instr.insert_after(instructions)
                    bytecode += instructions

            elif instr.opcode == Opcodes.STORE_DEREF:
                if instr.arg_value not in arg_decl_lookup:
                    continue

                arg_decl = arg_decl_lookup[instr.arg_value]

                if arg_decl.is_static:
                    instr.change_opcode(Opcodes.STORE_FAST, arg_names[arg_decl.index])
                else:
                    raise RuntimeError(
                        f"Tried to override non-static MACRO parameter '{instr.arg_value}'; This is not allowed as the parameter will be evaluated on each access!"
                    )

            elif instr.has_local() and instr.arg_value.startswith("MACRO_"):
                instr.change_arg_value(
                    local_prefix + ":" + instr.arg_value.removeprefix("MACRO_")
                )

        return bytecode

    def fill_scope(self, scope: ParsingScope):
        name = scope.scope_path + list(map(lambda e: e.text, self.name))
        namespace = name[:-1]
        inner_name = name[-1]
        namespace_level = scope.lookup_namespace(namespace)

        if inner_name not in namespace_level:
            page = self.MacroOverloadPage(name)
            namespace_level[inner_name] = page
        elif not isinstance(namespace_level[inner_name], self.MacroOverloadPage):
            raise RuntimeError(f"Expected <empty> or MacroOverloadPage, got {namespace_level[inner_name]}")
        else:
            page = namespace_level[inner_name]

        page.add_definition(self)


@Parser.register
class MacroPasteAssembly(AbstractAssemblyInstruction):
    # MACRO_PASTE <macro param name> ['->' <target>]
    NAME = "MACRO_PASTE"

    @classmethod
    def consume(cls, parser: "Parser") -> "MacroPasteAssembly":
        name = parser.consume(IdentifierToken)

        if parser.try_consume_multi([SpecialToken("-"), SpecialToken(">")]):
            target = parser.try_consume_access_token(allow_primitives=False)
        else:
            target = None

        return cls(name, target)

    def __init__(self, name: IdentifierToken, target: AbstractAccessExpression = None):
        self.name = name
        self.target = target

    def __repr__(self):
        return f"MACRO_PASTE({self.name.text}{'' if self.target is None else '-> '+repr(self.target)})"

    def __eq__(self, other):
        return type(self) == type(other) and self.name == other.name and self.target == other.target

    def copy(self) -> "MacroPasteAssembly":
        return type(self)(self.name, self.target.copy() if self.target else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, Opcodes.MACRO_PARAMETER_EXPANSION, self.name.text)
        ] + ([] if self.target is None else self.target.emit_store_bytecodes(function, scope))


@Parser.register
class MacroImportAssembly(AbstractAssemblyInstruction):
    # MACRO_IMPORT <module name with '.'> ['->' ['.'] <namespace with '.'>]
    NAME = "MACRO_IMPORT"

    @classmethod
    def consume(cls, parser: "Parser") -> "AbstractAssemblyInstruction":
        name = [parser.consume(IdentifierToken)]

        while parser.try_consume(SpecialToken(".")):
            name.append(parser.consume(IdentifierToken))

        is_relative_target = False

        if parser.try_consume_multi([SpecialToken("-"), SpecialToken(">")]):
            target = []

            if expr := parser.try_consume(IdentifierToken):
                target.append(expr)
            else:
                parser.save()
                parser.consume(SpecialToken("."))
                parser.rollback()
                is_relative_target = True

            while parser.try_consume(SpecialToken(".")):
                target.append(parser.consume(IdentifierToken))

        else:
            target = None

        return cls(
            name,
            target,
            is_relative_target,
        )

    def __init__(self, name: typing.List[IdentifierToken], target: typing.List[IdentifierToken] = None, is_relative_target: bool = False):
        self.name = name
        self.target = target
        self.is_relative_target = is_relative_target

    def __repr__(self):
        return f"MACRO_IMPORT('{'.'.join(map(lambda e: e.text, self.name))}'{'' if self.target is None else ('.' if self.is_relative_target else '') + '.'.join(map(lambda e: e.text, self.target))})"

    def __eq__(self, other):
        return type(self) == type(other) and self.name == other.name and self.target == other.target and self.is_relative_target == other.is_relative_target

    def copy(self) -> "MacroImportAssembly":
        return type(self)(self.name.copy(), self.target.copy(), self.is_relative_target)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return []

    def fill_scope(self, scope: ParsingScope):
        from bytecodemanipulation.assembler.Emitter import GLOBAL_SCOPE_CACHE

        if self.target is None:
            namespace = scope.scope_path
        elif self.is_relative_target:
            namespace = scope.scope_path + [e.text for e in self.target]
        else:
            namespace = [e.text for e in self.target]

        scope_entry = scope.lookup_namespace(namespace)
        
        module = ".".join(map(lambda e: e.text, self.name))
        
        if module not in GLOBAL_SCOPE_CACHE:
            __import__(module)

        if not scope_entry:
            scope_entry.update(GLOBAL_SCOPE_CACHE[module])

        else:
            tasks = [(scope_entry, GLOBAL_SCOPE_CACHE[module])]

            while tasks:
                target, source = tasks.pop(-1)

                for key in source.keys():
                    if key not in target:
                        target[key] = source[key]
                    elif isinstance(target[key], dict) and isinstance(source[key], dict):
                        tasks.append((target[key], source[key]))
                    else:
                        print(f"WARN: unknown integration stage: {source[key]} -> {target[key]}")
                        target[key] = source[key]
