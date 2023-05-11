import types
import typing
from abc import ABC

from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


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
        self.labels: typing.Set["IIdentifierAccessor"] = set()
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
        for entry in self.labels:
            if entry == name:
                return True

        return False

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

    def __init__(
        self,
        name: "IIdentifierAccessor | str",
        token: AbstractToken | typing.List[AbstractToken] = None,
    ):
        self.name = name
        self.token = token

    def __eq__(self, other):
        return type(self) == type(other) and self.name == other.name

    def __repr__(self):
        return f"{self.PREFIX}{self.name}"

    def copy(self) -> "AbstractAccessExpression":
        return type(self)(
            self.name, self.token.copy() if isinstance(self.token, list) else self.token
        )

    def get_static_value(self, scope: ParsingScope) -> typing.Any:
        raise ValueError("not implemented")

    def get_name(self, scope: ParsingScope):
        return self.name(scope) if not isinstance(self.name, str) else self.name


class JumpToLabel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"-> Label('{self.name}')"


class IIdentifierAccessor:
    def __call__(self, scope: ParsingScope):
        raise NotImplementedError


class MacroExpandedIdentifier(IIdentifierAccessor):
    def __init__(
        self,
        macro_name: typing.Union[str, "IIdentifierAccessor"],
        token: typing.List[AbstractToken] = None,
    ):
        self.macro_name = macro_name
        self.token = token

    def __hash__(self):
        return hash(self.macro_name)

    def __eq__(self, other):
        if isinstance(other, MacroExpandedIdentifier):
            return self.macro_name == other.macro_name
        return False

    def __repr__(self):
        return f"&{self.macro_name}"

    def __call__(self, scope: ParsingScope):
        from bytecodemanipulation.assembler.syntax_errors import (
            throw_positioned_syntax_error,
        )
        from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import (
            ConstantAccessExpression,
        )
        from bytecodemanipulation.data.shared.expressions.DerefAccessExpression import (
            DerefAccessExpression,
        )
        from bytecodemanipulation.data.shared.expressions.GlobalAccessExpression import (
            GlobalAccessExpression,
        )
        from bytecodemanipulation.data.shared.expressions.LocalAccessExpression import (
            LocalAccessExpression,
        )

        if scope is None:
            raise SyntaxError("no scope provided")

        if self.token[1].text not in scope.macro_parameter_namespace:
            raise throw_positioned_syntax_error(
                scope,
                self.token,
                "Could not find name in macro parameter space",
            )

        value = scope.macro_parameter_namespace[self.token[1].text]

        if isinstance(value, ConstantAccessExpression):
            if not isinstance(value.value, str):
                raise throw_positioned_syntax_error(
                    scope,
                    self.token,
                    f"Expected 'string' for name de-referencing, got {value}",
                )

            return value.value

        if isinstance(
            value,
            (
                GlobalAccessExpression,
                LocalAccessExpression,
                DerefAccessExpression,
            ),
        ):
            return value.get_name(scope)

        raise throw_positioned_syntax_error(
            scope,
            self.token,
            f"Expected <static evaluated expression> for getting the name for storing, got {value}",
        )


class StaticIdentifier(IIdentifierAccessor):
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return (
            isinstance(other, StaticIdentifier) and self.name == other.name
        ) or self.name == other

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return repr(self.name)

    def __call__(self, scope: ParsingScope):
        return self.name
