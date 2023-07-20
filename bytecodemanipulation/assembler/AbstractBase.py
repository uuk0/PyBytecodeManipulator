import copy
import types
import typing
from abc import ABC

from bytecodemanipulation.assembler.syntax_errors import TraceInfo
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.opcodes.Instruction import Instruction
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
        self.macro_parameter_namespace_stack: typing.List[typing.Dict[str]] = [{}]
        self.filled_locals = set()

        self.current_macro_assembly = None

        self.may_get_trace_info = False

        self.closure_locals: typing.Set[str] = set()

    def get_trace_info(self) -> TraceInfo:
        if not self.may_get_trace_info:
            raise RuntimeError("Cannot get trace info")

        return TraceInfo()

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
        shared_locals=True,
    ):
        instance = ParsingScope()
        if copy_labels:
            instance.labels = self.labels
        instance.global_scope = self.global_scope
        instance.scope_path = self.scope_path.copy()
        instance.module_file = self.module_file
        instance.macro_parameter_namespace_stack = [
            e.copy() for e in self.macro_parameter_namespace_stack
        ]

        if sub_scope_name is not None:
            if isinstance(sub_scope_name, str):
                instance.scope_path.append(sub_scope_name)
            else:
                instance.scope_path += sub_scope_name

        elif keep_scope_name_generator:
            instance.scope_name_generator = self.scope_name_generator

        if shared_locals:
            instance.filled_locals = self.filled_locals

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

    def lookup_macro_parameter(self, name: str, start: int = 0):
        for space in reversed(
            self.macro_parameter_namespace_stack[:-start]
            if start != 0
            else self.macro_parameter_namespace_stack
        ):
            if name in space:
                return space[name]

        raise KeyError(name)

    def lookup_macro_parameter_with_level(
        self, name: str, start: int = 0
    ) -> typing.Tuple[typing.Any, int]:
        for i, space in enumerate(
            list(
                reversed(
                    self.macro_parameter_namespace_stack[:-start]
                    if start != 0
                    else self.macro_parameter_namespace_stack
                )
            )
        ):
            if name in space:
                return space[name], i

        raise KeyError(name)

    def set_macro_arg_value(self, key: str, value: typing.Any):
        self.macro_parameter_namespace_stack[-1][key] = value

    def push_macro_param_stack(self):
        self.macro_parameter_namespace_stack.append({})

    def pop_macro_param_stack(self):
        self.macro_parameter_namespace_stack.pop(-1)


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

    def evaluate_static_value(self, scope: ParsingScope) -> typing.Any:
        raise NotImplementedError

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return tuple()


class AbstractAccessExpression(AbstractSourceExpression, ABC):
    PREFIX: str | None = None
    IS_STATIC = False

    def __init__(
        self,
        name: "IIdentifierAccessor | str",
        token: AbstractToken | typing.List[AbstractToken] = None,
        trace_info: TraceInfo = None,
    ):
        self.name = name if not isinstance(name, str) else StaticIdentifier(name)
        self.token = token
        self.trace_info: TraceInfo = trace_info

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

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return tuple()


class MacroExpandedIdentifier(IIdentifierAccessor):
    def __init__(
        self,
        macro_name: typing.Union[str, "IIdentifierAccessor"],
        token: typing.List[AbstractToken] = None,
    ):
        self.macro_name = macro_name
        self.token = token
        self.trace_info: TraceInfo = None

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return self.token

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
            PropagatingCompilerException,
        )

        if scope is None:
            return f"<context dependent on macro name {self.token[1].text}>"

        try:
            value = scope.lookup_macro_parameter(self.token[1].text)
        except KeyError:
            raise PropagatingCompilerException(
                f"Could not find name '{self.token[1].text}' in macro parameter space"
            ).add_trace_level(self.trace_info.with_token(self.token[1])) from None

        return self._check_value(scope, value)

    def _check_value(self, scope, value, level=1):
        from bytecodemanipulation.assembler.syntax_errors import (
            PropagatingCompilerException,
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

        if isinstance(value, ConstantAccessExpression):
            if not isinstance(value.value, str):
                raise PropagatingCompilerException(
                    f"Expected 'string' for name de-referencing, got '{value}'"
                ).add_trace_level(self.trace_info.with_token(self.token[0]))

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

        from bytecodemanipulation.data.shared.expressions.MacroParameterAcessExpression import (
            MacroParameterAccessExpression,
        )

        if isinstance(value, MacroParameterAccessExpression):
            new_value = scope.lookup_macro_parameter(value.name(scope), start=level)

            if value != new_value:
                return self._check_value(scope, new_value, level=level + 1)

            print("WARN: got some value from macro namespace")

        raise PropagatingCompilerException(
            f"Expected <static evaluated expression> for getting the name for storing, got '{value}'"
        ).add_trace_level(self.trace_info.with_token(self.token[0])) from None


class StaticIdentifier(IIdentifierAccessor):
    def __init__(self, name: str, token: AbstractToken = None):
        self.name = name
        self.token = token

    def __eq__(self, other):
        return (
            isinstance(other, StaticIdentifier) and self.name == other.name
        ) or self.name == other

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return "!" + repr(self.name)

    def __call__(self, scope: ParsingScope):
        return self.name

    def get_tokens(self) -> typing.Iterable[AbstractToken]:
        return (self.token,)
