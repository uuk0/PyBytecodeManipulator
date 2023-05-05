import builtins
import copy
import sys
import types
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


LOCAL_TO_DEREF_OPCODES = {Opcodes.LOAD_FAST: Opcodes.LOAD_DEREF, Opcodes.STORE_FAST: Opcodes.STORE_DEREF}


class ParsingScope:
    @classmethod
    def create_for_module(cls, module: types.ModuleType):
        scope = cls()
        scope.globals_dict = module.__dict__
        scope.module_file = module.__globals__

        from bytecodemanipulation.assembler.Emitter import GLOBAL_SCOPE_CACHE

        if module.__module__ in GLOBAL_SCOPE_CACHE:
            scope.global_scope = GLOBAL_SCOPE_CACHE[module.__module__]
        else:
            GLOBAL_SCOPE_CACHE[module.__module__] = scope.global_scope

        return scope

    @classmethod
    def create_for_function(cls, target: typing.Callable):
        scope = cls()
        scope.globals_dict = target.__globals__
        scope.module_file = target.__globals__["__file__"]

        from bytecodemanipulation.assembler.Emitter import GLOBAL_SCOPE_CACHE

        if target.__module__ in GLOBAL_SCOPE_CACHE:
            scope.global_scope = GLOBAL_SCOPE_CACHE[target.__module__]
        else:
            GLOBAL_SCOPE_CACHE[target.__module__] = scope.global_scope

        return scope

    def __init__(self):
        self.labels: typing.Set[str] = set()
        self.global_scope = {}
        self.scope_path: typing.List[str] = []
        self._name_counter = 1
        self.globals_dict = {}
        self.module_file: str = None
        self.last_base_token: AbstractToken = None
        self.macro_parameter_namespace: typing.Dict[str] = {}

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

    def lookup_namespace(
        self, name: typing.List[str], create=True, include_prefixes=False
    ):
        if include_prefixes:
            for i in range(len(self.scope_path) + 1):
                if space := self.lookup_namespace(
                    self.scope_path[:i] + name, create=False
                ):
                    return space

            if not create:
                return

        if create:
            scope = self.global_scope

            for e in name:
                scope = scope.setdefault(e, {})

            return scope

        else:
            scope = self.global_scope

            for e in name:
                if e in scope:
                    scope = scope[e]
                else:
                    return

            return scope

    def exists_label(self, name: str) -> bool:
        return name in self.labels

    def copy(
        self,
        sub_scope_name: str | list = None,
        copy_labels=False,
        keep_scope_name_generator: bool = None,
    ):
        instance = ParsingScope()
        if copy_labels:
            instance.labels = self.labels
        instance.global_scope = self.global_scope
        instance.scope_path = self.scope_path.copy()
        instance.module_file = self.module_file
        instance.macro_parameter_namespace = self.macro_parameter_namespace.copy()

        if sub_scope_name is not None:
            if isinstance(sub_scope_name, str):
                instance.scope_path.append(sub_scope_name)
            else:
                instance.scope_path += sub_scope_name

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


def _print_complex_token_location(
    scope: ParsingScope,
    tokens: typing.List[AbstractToken | None],
    exc_type: typing.Type[Exception] = SyntaxError,
):
    lines: typing.Dict[int, typing.List[AbstractToken]] = {}

    with open(scope.module_file, mode="r", encoding="utf-8") as f:
        content = f.readlines()

    for token in tokens:
        if token:
            lines.setdefault(token.line, []).append(token)

    already_seen_line = False
    previous_line_no = -2

    for line in sorted(list(lines.keys())):
        tokens = lines[line]
        tokens.sort(key=lambda t: t.column)

        error_location = ""

        for token in tokens:
            if token.column > len(error_location):
                error_location += " " * (token.column - len(error_location))

            delta = len(error_location) - token.column

            if delta >= token.span:
                continue

            error_location += "^" + ("~" * (token.span - delta))

        error_location = error_location.replace("^^", "^~").replace("~^", "~~")

        if line != previous_line_no + 1:
            if already_seen_line:
                print()
            already_seen_line = True

            file = scope.module_file.replace("\\", "/")
            print(f'File "{file}", line {line + 1}', file=sys.stderr)
        previous_line_no = line

        print(content[line].removesuffix("\n"), file=sys.stderr)
        print(error_location, file=sys.stderr)


def throw_positioned_syntax_error(
    scope: ParsingScope,
    token: AbstractToken | typing.List[AbstractToken | None] | None,
    message: str,
    exc_type: typing.Type[Exception] = SyntaxError,
) -> Exception:
    if scope and scope.module_file and token:
        if isinstance(token, list):
            _print_complex_token_location(scope, token, exc_type=exc_type)
        else:
            file = scope.module_file.replace("\\", "/")
            print(f'File "{file}", line {token.line+1}', file=sys.stderr)
            with open(scope.module_file, mode="r", encoding="utf-8") as f:
                content = f.readlines()

            line = content[token.line]
            print(line.rstrip(), file=sys.stderr)
            print(
                (" " * token.column) + "^" + ("~" * (token.span - 1)), file=sys.stderr
            )

        print(f"-> {exc_type.__name__}: {message}", file=sys.stderr)
    else:
        # print(scope, scope.module_file if scope else None, token)
        return exc_type(f"{token}: {message}")

    return exc_type(message)


def _syntax_wrapper(token, text, scope):
    raise throw_positioned_syntax_error(scope, token, text)


parser_file.raise_syntax_error = _syntax_wrapper


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
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractAssemblyInstruction":
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
    IS_STATIC = False

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

    def get_static_value(self, scope: ParsingScope) -> typing.Any:
        raise ValueError("not implemented")


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

    def get_static_value(self, scope: ParsingScope) -> typing.Any:
        raise ValueError("not implemented")


class GlobalStaticAccessExpression(AbstractAccessExpression):
    PREFIX = "@!"
    IS_STATIC = True

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        key = self.name_token.text
        global_dict = function.target.__globals__
        if key not in global_dict and hasattr(builtins, key):
            value = getattr(builtins, key)
        else:
            value = global_dict.get(key)

        return [
            Instruction.create_with_token(
                self.name_token, function, -1, "LOAD_CONST", value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError("Cannot assign to a constant global")

    def get_static_value(self, scope: ParsingScope) -> typing.Any:
        if self.name_token.text in scope.globals_dict:
            return scope.globals_dict[self.name_token]

        raise throw_positioned_syntax_error(
            scope,
            self.name_token,
            f"Name {self.name_token.text} not found!",
            NameError,
        )


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

        if value in scope.macro_parameter_namespace and hasattr(scope.macro_parameter_namespace[value], "emit_bytecodes") and scope.macro_parameter_namespace[value] != self:
            return scope.macro_parameter_namespace[value].emit_bytecodes(function, scope)

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

        if value in scope.macro_parameter_namespace and hasattr(scope.macro_parameter_namespace[value], "emit_bytecodes"):
            return scope.macro_parameter_namespace[value].emit_store_bytecodes(function, scope)

        print(scope.macro_parameter_namespace[value])

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
    IS_STATIC = True

    def __init__(self, value, token: AbstractToken = None):
        self.value = value
        self.token = token

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.value == other.value

    def __repr__(self):
        return f"CONSTANT({repr(self.value)})"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(copy.deepcopy(self.value))

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [Instruction(function, -1, "LOAD_CONST", self.value)]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise throw_positioned_syntax_error(
            scope, self.token, f"Cannot assign to a constant: {self}"
        )


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
            + [Instruction(function, -1, Opcodes.BINARY_SUBSCR)]
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
        return visitor(
            self, (self.root.visit_parts(visitor, parents + [self]),), parents
        )


class StaticAttributeAccessExpression(AbstractAccessExpression):
    IS_STATIC = True

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
        return f"{self.root}.!{self.name_token.text}"

    def copy(self) -> "AttributeAccessExpression":
        return AttributeAccessExpression(self.root.copy(), self.name_token)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return self.root.emit_bytecodes(function, scope) + [
            Instruction.create_with_token(
                self.name_token,
                function,
                -1,
                "STATIC_ATTRIBUTE_ACCESS",
                self.name_token.text,
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

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


class ModuleAccessExpression(AbstractAccessExpression):
    IS_STATIC = True
    PREFIX = "~"
    _CACHE = builtins.__dict__.copy()

    @classmethod
    def _cached_lookup(cls, module_name: str) -> types.ModuleType:
        if module_name not in cls._CACHE:
            module = cls._CACHE[module_name] = __import__(module_name)
            return module

        return cls._CACHE[module_name]

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        value = self._cached_lookup(self.name_token.text)
        return [
            Instruction.create_with_token(
                self.name_token, function, -1, Opcodes.LOAD_CONST, value
            )
        ]

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def get_static_value(self, scope: ParsingScope) -> typing.Any:
        return self._cached_lookup(self.name_token.text)


class AbstractCallAssembly(AbstractAssemblyInstruction, AbstractAccessExpression, ABC):
    INSTANCE: typing.Type["AbstractCallAssembly"] | None = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        AbstractCallAssembly.INSTANCE = cls

    @classmethod
    def construct_from_partial(cls, access: AbstractAccessExpression, parser: "Parser", scope: ParsingScope):
        raise NotImplementedError


class DiscardValue(AbstractAccessExpression):
    def __init__(self):
        pass

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        raise RuntimeError

    def emit_store_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        return [
            Instruction(function, -1, Opcodes.POP_TOP)
        ]


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
        self.scope = scope or self.scope
        return self.parse_while_predicate(
            lambda: not self.is_empty(), scope=scope or self.scope
        )

    def parse_body(
        self, namespace_part: str | list | None = None, scope: ParsingScope = None
    ) -> CompoundExpression:
        if namespace_part is not None:
            if isinstance(namespace_part, str):
                self.scope.scope_path.append(namespace_part)
            else:
                self.scope.scope_path += namespace_part

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
                if self.scope.scope_path.pop() != namespace_part:
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
                    return MacroAssembly.consume_call(self, scope)

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

        if not isinstance(start_token, (SpecialToken, IdentifierToken)):
            return

        if start_token.text == "@":
            self.consume(SpecialToken("@"), err_arg=scope)

            if self.try_consume(SpecialToken("!")):
                expr = GlobalStaticAccessExpression(
                    self.consume([IdentifierToken, IntegerToken])
                )
            else:
                expr = GlobalAccessExpression(
                    self.consume([IdentifierToken, IntegerToken])
                )

        elif start_token.text == "$":
            self.consume(SpecialToken("$"), err_arg=scope)
            expr = LocalAccessExpression(self.consume([IdentifierToken, IntegerToken]))

        elif start_token.text == "§":
            self.consume(SpecialToken("§"), err_arg=scope)
            expr = DerefAccessExpression(self.consume([IdentifierToken, IntegerToken]))

        elif start_token.text == "%" and allow_tos:
            self.consume(SpecialToken("%"), err_arg=scope)
            expr = TopOfStackAccessExpression()

        elif start_token.text == "~":
            self.consume(SpecialToken("~"), err_arg=scope)
            expr = ModuleAccessExpression(self.consume(IdentifierToken))

        elif start_token.text == "\\":
            self.consume(SpecialToken("\\"), err_arg=scope)
            expr = DiscardValue()

        elif start_token.text == "OP" and allow_op and "OP" in self.INSTRUCTIONS:
            self.consume(start_token)
            self.consume(SpecialToken("("), err_arg=scope)
            expr = self.INSTRUCTIONS["OP"].consume(self, scope)
            self.consume(SpecialToken(")"), err_arg=scope)

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
                    if self.try_consume(SpecialToken("(")):
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
                                    if not isinstance(
                                        self.try_inspect(), IdentifierToken
                                    )
                                    else " (did you forget a prefix?)"
                                ),
                            )

                        if not self.try_consume(SpecialToken(")")):
                            raise throw_positioned_syntax_error(
                                scope, self.try_inspect() or self[-1], "expected ')'"
                            )

                        expr = DynamicAttributeAccessExpression(expr, index)
                    elif self.try_consume(SpecialToken("!")):
                        name = self.try_consume(IdentifierToken)
                        expr = StaticAttributeAccessExpression(expr, name)
                    else:
                        name = self.try_consume(IdentifierToken)
                        expr = AttributeAccessExpression(expr, name)

                elif self.try_inspect() == SpecialToken("(") and allow_calls:
                    expr = AbstractCallAssembly.INSTANCE.construct_from_partial(expr, self, scope)

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


@Parser.register
class LabelAssembly(AbstractAssemblyInstruction):
    # LABEL <name>
    NAME = "LABEL"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "LabelAssembly":
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
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "PythonCodeAssembly":
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
    # 'NAMESPACE' [{<namespace> ':'}] <name> '{' <code> '}'
    NAME = "NAMESPACE"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "NamespaceAssembly":
        name = [parser.consume(IdentifierToken)]

        while parser.try_consume(SpecialToken(":")):
            name.append(parser.consume(IdentifierToken))

        assembly = parser.parse_body(namespace_part=[e.text for e in name], scope=scope)

        return cls(
            name,
            assembly,
        )

    def __init__(
        self, name: typing.List[IdentifierToken], assembly: CompoundExpression
    ):
        self.name = name
        self.assembly = assembly

    def __repr__(self):
        return (
            f"NAMESPACE::'{':'.join(e.text for e in self.name)}'({repr(self.assembly)})"
        )

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
            function, scope.copy(sub_scope_name=[e.text for e in self.name])
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

    class AbstractDataType(ABC):
        IDENTIFIER: str = None

        def is_match(
            self,
            arg: "MacroAssembly.MacroArg",
            arg_accessor: AbstractAccessExpression | CompoundExpression,
        ) -> bool:
            raise NotImplementedError

        def emit_for_arg(
            self,
            arg: AbstractAccessExpression,
            function: MutableFunction,
            scope: ParsingScope,
        ) -> typing.List[Instruction]:
            return arg.emit_bytecodes(function, scope)

        def emit_for_arg_store(
            self,
            arg: AbstractAccessExpression,
            function: MutableFunction,
            scope: ParsingScope,
        ) -> typing.List[Instruction] | None:
            pass

    class CodeBlockDataType(AbstractDataType):
        IDENTIFIER = "CODE_BLOCK"

        def is_match(
            self,
            arg: "MacroAssembly.MacroArg",
            arg_accessor: AbstractAccessExpression | CompoundExpression,
        ) -> bool:
            return isinstance(arg_accessor, CompoundExpression)

    class VariableDataType(AbstractDataType):
        IDENTIFIER = "VARIABLE"
        VALID_ACCESSOR_TYPES = [
            GlobalAccessExpression,
            LocalAccessExpression,
            DerefAccessExpression,
        ]

        def is_match(
            self,
            arg: "MacroAssembly.MacroArg",
            arg_accessor: AbstractAccessExpression | CompoundExpression,
        ) -> bool:
            return isinstance(arg_accessor, tuple(self.VALID_ACCESSOR_TYPES))

        def emit_for_arg_store(
            self,
            arg: AbstractAccessExpression,
            function: MutableFunction,
            scope: ParsingScope,
        ) -> typing.List[Instruction] | None:
            return arg.emit_store_bytecodes(function, scope)

    class VariableArgCountDataType(AbstractDataType):
        IDENTIFIER = "VARIABLE_ARG"

        def __init__(self, sub_type: typing.Optional["MacroAssembly.AbstractDataType"]):
            self.sub_type = sub_type

        def is_match(
            self,
            arg: "MacroAssembly.MacroArg",
            arg_accessor: AbstractAccessExpression | CompoundExpression,
        ) -> bool:
            return self.sub_type is None or self.sub_type.is_match(arg, arg_accessor)

        def emit_for_arg(
            self,
            args: typing.List[AbstractAccessExpression],
            function: MutableFunction,
            scope: ParsingScope,
        ) -> typing.List[Instruction]:
            if not isinstance(args, list):
                raise ValueError(f"args must be list, got {args}!")

            bytecode = []
            for arg in args:
                bytecode += arg.emit_bytecodes(function, scope)

            bytecode += [Instruction(function, -1, "BUILD_LIST", arg=len(args))]
            return bytecode

    class MacroArg:
        def __init__(self, name: IdentifierToken, is_static=False):
            self.name = name
            self.is_static = is_static
            self.index = -1
            self.data_type_annotation: MacroAssembly.AbstractDataType = None

        def copy(self):
            return type(self)(self.name, self.is_static)

        def is_match(
            self, arg_accessor: AbstractAccessExpression | CompoundExpression
        ) -> bool:
            if self.data_type_annotation is None:
                return True

            if isinstance(self.data_type_annotation, MacroAssembly.AbstractDataType):
                return self.data_type_annotation.is_match(self, arg_accessor)

            return False

    class MacroOverloadPage:
        def __init__(
            self,
            name: typing.List[str],
            name_token: typing.List[IdentifierToken] = None,
        ):
            self.name = name
            self.name_token = name_token
            self.assemblies: typing.List[MacroAssembly] = []

        def add_assembly(self, assembly: "MacroAssembly"):
            self.assemblies.append(assembly)
            return self

        def __repr__(self) -> str:
            return f"MACRO_OVERLOAD({'::'.join(self.name)}, [{', '.join(map(repr, self.assemblies))}])"

        def lookup(
            self,
            args: typing.List[AbstractAccessExpression],
            scope: ParsingScope,
        ) -> typing.Tuple["MacroAssembly", list]:
            for macro in self.assemblies:
                # todo: better check here!
                has_star_args = any(
                    isinstance(
                        e.data_type_annotation, MacroAssembly.VariableArgCountDataType
                    )
                    for e in macro.args
                )

                if (
                    len(macro.args) == len(args)
                    and all(arg.is_match(param) for arg, param in zip(macro.args, args))
                    and not has_star_args
                ):
                    return macro, args

                if has_star_args:
                    error = False
                    prefix = []
                    inner = []
                    postfix = []

                    # Get all args before the VARIABLE_ARG
                    i = 0
                    for i, e in enumerate(macro.args):
                        if isinstance(
                            e.data_type_annotation,
                            MacroAssembly.VariableArgCountDataType,
                        ):
                            break

                        if not e.is_match(args[i]):
                            error = True
                            break

                        prefix.append(args[i])

                    star_index = i

                    if error:
                        continue

                    # Get all args after the VARIABLE_ARG
                    i = 0
                    for i in range(-len(macro.args), 0):
                        if isinstance(
                            e.data_type_annotation,
                            MacroAssembly.VariableArgCountDataType,
                        ):
                            break

                        if not e.is_match(args[i]):
                            error = True
                            break

                        postfix.insert(0, args[i])

                    # todo: assert that the current i is equal to the star_index

                    if error:
                        continue

                    # And now collect the args in between
                    for arg in (
                        args[star_index : i + 1] if i != -1 else args[star_index:]
                    ):
                        if not macro.args[star_index].is_match(arg):
                            error = True
                            break

                        inner.append(arg)

                    if error:
                        continue

                    args[:] = prefix + [inner] + postfix
                    return macro, args

            raise throw_positioned_syntax_error(
                scope,
                self.name_token,
                f"Could not find overloaded variant of {':'.join(self.name)} with args {args}!",
                NameError,
            )

        def add_definition(self, macro: "MacroAssembly", override=False):
            # todo: do a safety check!
            self.assemblies.append(macro)

    @classmethod
    def _try_parse_arg_data_type(cls, parser: Parser) -> AbstractDataType | None:
        if identifier := parser.try_consume(IdentifierToken):
            if identifier.text == "CODE_BLOCK":
                inst = cls.CodeBlockDataType()
                return inst

            elif identifier.text == "VARIABLE_ARG":
                # todo: add check that it is the only * arg
                if parser.try_consume(SpecialToken("[")):
                    inner_type = cls._try_parse_arg_data_type(parser)
                    if inner_type is None:
                        return

                    inst = cls.VariableArgCountDataType(inner_type)
                    parser.consume(SpecialToken("]"))
                else:
                    inst = cls.VariableArgCountDataType(None)

                return inst

            elif identifier.text == "VARIABLE":
                inst = cls.VariableDataType()
                return inst

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "MacroAssembly":
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

                data_type = cls._try_parse_arg_data_type(parser)

                parser.save()
                if data_type is not None:
                    arg.data_type_annotation = data_type
                    parser.discard_save()
                else:
                    parser.rollback()

                if not parser.try_consume(SpecialToken(",")):
                    parser.consume(SpecialToken(")"))
                    break

        body = parser.parse_body(scope=scope)

        return cls(
            name,
            args,
            body,
            allow_assembly_instr,
            scope_path=scope.scope_path.copy(),
            module_path=scope.module_file,
        )

    @classmethod
    def consume_call(
        cls, parser: Parser, scope: ParsingScope
    ) -> AbstractAssemblyInstruction:
        raise RuntimeError

    def __init__(
        self,
        name: typing.List[IdentifierToken],
        args: typing.List[MacroArg],
        body: CompoundExpression,
        allow_assembly_instr=False,
        scope_path: typing.List[str] = None,
        module_path: str = None,
    ):
        self.name = name
        self.args = args
        self.body = body
        self.allow_assembly_instr = allow_assembly_instr
        self.scope_path = scope_path or []
        self.module_path = module_path

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

        scope = scope.copy()
        scope.scope_path = self.scope_path
        scope.module_file = self.module_path

        bytecode = []

        for arg_decl, arg_code in zip(self.args, args):
            if arg_decl.is_static:
                scope.macro_parameter_namespace[arg_decl.name.text] = arg_decl.name.text
            else:
                scope.macro_parameter_namespace[arg_decl.name.text] = arg_code

        inner_bytecode = self.body.emit_bytecodes(function, scope)

        arg_names: typing.List[str | None] = []
        arg_decl_lookup: typing.Dict[str, MacroAssembly.MacroArg] = {}
        for i, (arg_decl, arg_code) in enumerate(zip(self.args, args)):
            arg_decl_lookup[arg_decl.name.text] = arg_decl
            if arg_decl.is_static:
                if arg_decl.data_type_annotation is not None:
                    arg_names.append(var_name := scope.scope_name_generator(f"arg_{i}"))
                    bytecode += arg_decl.data_type_annotation.emit_for_arg(
                        arg_code, function, scope
                    )
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

                arg_decl: MacroAssembly.MacroArg = arg_decl_lookup[instr.arg_value]

                if arg_decl.data_type_annotation is not None:
                    if arg_decl.is_static:
                        instr.change_opcode(
                            Opcodes.LOAD_FAST, arg_names[arg_decl.index]
                        )

                    else:
                        instr.change_opcode(Opcodes.NOP)
                        instructions = arg_decl.data_type_annotation.emit_for_arg(
                            args[arg_decl.index], function, scope
                        )
                        instr.insert_after(instructions)
                        bytecode += instructions

                else:
                    if arg_decl.is_static:
                        instr.change_opcode(
                            Opcodes.LOAD_FAST, arg_names[arg_decl.index]
                        )

                    else:
                        instr.change_opcode(Opcodes.NOP)
                        instructions = args[arg_decl.index].emit_bytecodes(
                            function, scope
                        )
                        instr.insert_after(instructions)
                        bytecode += instructions

            elif instr.opcode == Opcodes.STORE_DEREF:
                if instr.arg_value not in arg_decl_lookup:
                    continue

                arg_decl = arg_decl_lookup[instr.arg_value]

                if arg_decl.is_static:
                    instr.change_opcode(Opcodes.STORE_FAST, arg_names[arg_decl.index])
                else:
                    if arg_decl.data_type_annotation is not None:
                        instructions = arg_decl.data_type_annotation.emit_for_arg_store(
                            args[arg_decl.index], function, scope
                        )

                        if instructions is not None:
                            instr.change_opcode(Opcodes.NOP)
                            instr.insert_after(instructions)
                            bytecode += instructions
                            continue

                    raise throw_positioned_syntax_error(
                        scope,
                        self.name,
                        f"Tried to override non-static MACRO parameter '{instr.arg_value}'; This is not allowed as the parameter will be evaluated on each access!",
                        RuntimeError,
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
            page = self.MacroOverloadPage(name, self.name)
            namespace_level[inner_name] = page
        elif not isinstance(namespace_level[inner_name], self.MacroOverloadPage):
            raise RuntimeError(
                f"Expected <empty> or MacroOverloadPage, got {namespace_level[inner_name]}"
            )
        else:
            page = namespace_level[inner_name]

        page.add_definition(self)

    class Function2CompoundMapper(CompoundExpression):
        def __init__(self, function: typing.Callable, scoped_names: typing.List[str] = None):
            super().__init__([])
            self.function = MutableFunction(function)
            self.scoped_names = scoped_names or []

        def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
            macro_exit_label = scope.scope_name_generator("macro_exit")
            return [
                (
                    instr.copy(owner=function)
                    if instr.opcode != Opcodes.RETURN_VALUE
                    else
                    instr.copy(owner=function).change_opcode(
                        Opcodes.POP_TOP).insert_after(Instruction(
                        function, -1, Opcodes.JUMP_ABSOLUTE, JumpToLabel(macro_exit_label)))
                )
                if not instr.has_local() or instr.arg_value not in self.scoped_names
                else instr.copy(owner=function).change_opcode(LOCAL_TO_DEREF_OPCODES[instr.opcode])
                for instr in self.function.instructions
            ] + [
                Instruction(function, -1, Opcodes.BYTECODE_LABEL, macro_exit_label)
            ]



@Parser.register
class MacroPasteAssembly(AbstractAssemblyInstruction):
    # MACRO_PASTE <macro param name> ['->' <target>]
    NAME = "MACRO_PASTE"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "MacroPasteAssembly":
        # Parse an optional § infront of the name
        parser.try_consume(SpecialToken("§"))

        name = parser.consume(IdentifierToken)

        if parser.try_consume_multi([SpecialToken("-"), SpecialToken(">")]):
            target = parser.try_consume_access_to_value(
                allow_primitives=False, scope=scope
            )
        else:
            target = None

        return cls(name, target)

    def __init__(self, name: IdentifierToken, target: AbstractAccessExpression = None):
        self.name = name
        self.target = target

    def __repr__(self):
        return f"MACRO_PASTE({self.name.text}{'' if self.target is None else '-> '+repr(self.target)})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name == other.name
            and self.target == other.target
        )

    def copy(self) -> "MacroPasteAssembly":
        return type(self)(self.name, self.target.copy() if self.target else None)

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        if self.name.text in scope.macro_parameter_namespace and hasattr(scope.macro_parameter_namespace[self.name.text], "emit_bytecodes"):
            return scope.macro_parameter_namespace[self.name.text].emit_bytecodes(function, scope) + (
                []
                if self.target is None
                else self.target.emit_store_bytecodes(function, scope)
            )

        return [
            Instruction(function, -1, Opcodes.MACRO_PARAMETER_EXPANSION, self.name.text)
        ] + (
            []
            if self.target is None
            else self.target.emit_store_bytecodes(function, scope)
        )


@Parser.register
class MacroImportAssembly(AbstractAssemblyInstruction):
    # MACRO_IMPORT <module name with '.'> ['->' ['.'] <namespace with '.'>]
    NAME = "MACRO_IMPORT"

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractAssemblyInstruction":
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

    def __init__(
        self,
        name: typing.List[IdentifierToken],
        target: typing.List[IdentifierToken] = None,
        is_relative_target: bool = False,
    ):
        self.name = name
        self.target = target
        self.is_relative_target = is_relative_target

    def __repr__(self):
        return f"MACRO_IMPORT('{'.'.join(map(lambda e: e.text, self.name))}'{'' if self.target is None else ('.' if self.is_relative_target else '') + '.'.join(map(lambda e: e.text, self.target))})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.name == other.name
            and self.target == other.target
            and self.is_relative_target == other.is_relative_target
        )

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
                    elif target[key] == source[key]:
                        pass
                    elif isinstance(target[key], dict) and isinstance(
                        source[key], dict
                    ):
                        tasks.append((target[key], source[key]))

                    # todo: can we use something like this?
                    # elif isinstance(target[key], MacroAssembly.MacroOverloadPage) and isinstance(source[key], MacroAssembly.MacroOverloadPage):
                    #     target[key].integrate(source[key])

                    else:
                        print(
                            f"WARN: unknown integration stage: {source[key]} -> {target[key]}"
                        )
                        target[key] = source[key]
