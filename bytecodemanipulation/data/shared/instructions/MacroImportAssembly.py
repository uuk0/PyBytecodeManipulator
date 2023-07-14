import traceback
import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.syntax_errors import (
    PropagatingCompilerException,
    TraceInfo,
)
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.instructions.MacroAssembly import MacroAssembly
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class MacroImportAssembly(AbstractAssemblyInstruction):
    # MACRO_IMPORT <module name with '.'> ['->' [':'] <namespace with ':'>]
    NAME = "MACRO_IMPORT"

    @classmethod
    def register(cls):
        Parser.register(cls)

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractAssemblyInstruction":
        name = [parser.consume(IdentifierToken)]

        while sep := parser.try_consume(SpecialToken(".")):
            if not (expr := parser.consume(IdentifierToken)):
                raise PropagatingCompilerException(
                    "expected <identifier> after '.' in <source> of MACRO_IMPORT"
                ).add_trace_level(scope.get_trace_info().with_token(name, sep))

            name.append(expr)

        is_relative_target = False

        if arrow_0 := parser.try_consume(SpecialToken("-")):
            if not (arrow_1 := parser.try_consume(SpecialToken(">"))):
                raise PropagatingCompilerException(
                    "expected '>' after '-' to complete <target>-expression in MACRO_IMPORT"
                ).add_trace_level(scope.get_trace_info().with_token(arrow_0, parser[0]))

            relative_target_token = parser.try_consume(SpecialToken(":"))
            is_relative_target = bool(relative_target_token)

            if not (expr := parser.try_consume(IdentifierToken)):
                raise PropagatingCompilerException(
                    f"expected <expression> {' or :' if is_relative_target else ''} after '->' in MACRO_IMPORT"
                ).add_trace_level(scope.get_trace_info().with_token(arrow_0, arrow_1, parser[0], relative_target_token))

            target = [expr]
            while sep := parser.try_consume(SpecialToken(":")):
                if not (expr := parser.try_consume(IdentifierToken)):
                    raise PropagatingCompilerException(
                        "expected <expression> after ':' in <target> of MACRO_IMPORT"
                    ).add_trace_level(scope.get_trace_info().with_token(arrow_0, arrow_1, target, sep))

                target.append(expr)

        else:
            target = None

        return cls(
            name,
            target,
            is_relative_target=is_relative_target,
            trace_info=scope.get_trace_info().with_token(name),
        )

    def __init__(
        self,
        name: typing.List[IdentifierToken],
        target: typing.List[IdentifierToken] = None,
        is_relative_target: bool = False,
        trace_info: TraceInfo = None,
    ):
        self.name = name
        self.target = target
        self.is_relative_target = is_relative_target
        self.trace_info = trace_info

    def __repr__(self):
        return f"MACRO_IMPORT('{'.'.join(map(lambda e: e.text, self.name))}'{'' if self.target is None else (':' if self.is_relative_target else '') + ':'.join(map(lambda e: e.text, self.target))})"

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
        # sourcery skip: remove-redundant-if, remove-unreachable-code
        from bytecodemanipulation.assembler.Emitter import GLOBAL_SCOPE_CACHE
        import bytecodemanipulation.assembler.hook

        if self.target is None:
            namespace = scope.scope_path
        elif self.is_relative_target:
            namespace = scope.scope_path + [e.text for e in self.target]
        else:
            namespace = [e.text for e in self.target]

        scope_entry = scope.lookup_namespace(namespace)

        module = ".".join(map(lambda e: e.text, self.name))

        if module not in GLOBAL_SCOPE_CACHE:
            prev = bytecodemanipulation.assembler.hook.LET_PROPAGATE_EXCEPTIONS_THROUGH
            bytecodemanipulation.assembler.hook.LET_PROPAGATE_EXCEPTIONS_THROUGH = True

            try:
                __import__(module)
            except PropagatingCompilerException as e:
                e.add_trace_level(self.trace_info)
                raise e
            except Exception as e:
                traceback.print_exc()
                raise PropagatingCompilerException(
                    "MACRO_IMPORT failed due to the normal import failing", *e.args
                ).set_underlying_exception(type(e)).add_trace_level(
                    self.trace_info
                ) from None

            bytecodemanipulation.assembler.hook.LET_PROPAGATE_EXCEPTIONS_THROUGH = prev

        if not scope_entry:
            if module not in GLOBAL_SCOPE_CACHE:
                raise PropagatingCompilerException(
                    f"could not find module '{module}' (tried to import it, but it did not expose any namespace data)"
                ).add_trace_level(self.trace_info)

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
                    elif isinstance(target[key], MacroAssembly.MacroOverloadPage) and isinstance(source[key], MacroAssembly.MacroOverloadPage):
                        target[key].integrate(source[key])

                    else:
                        print(
                            f"WARN: unknown integration stage: {source[key]} -> {target[key]}"
                        )
                        target[key] = source[key]
