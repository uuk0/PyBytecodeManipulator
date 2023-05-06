import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class MacroImportAssembly(AbstractAssemblyInstruction):
    # MACRO_IMPORT <module name with '.'> ['->' ['.'] <namespace with '.'>]
    NAME = "MACRO_IMPORT"

    @classmethod
    def register(cls):
        Parser.register(cls)

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
