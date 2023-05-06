import typing
from abc import ABC

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
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
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


LOCAL_TO_DEREF_OPCODES = {
    Opcodes.LOAD_FAST: Opcodes.MACRO_LOAD_PARAMETER,
    Opcodes.STORE_FAST: Opcodes.MACRO_STORE_PARAMETER,
}


class MacroAssembly(AbstractAssemblyInstruction):
    # 'MACRO' ['ASSEMBLY'] [{<namespace> ':'}] <name> ['(' <param> \[{',' <param>}] ')'] ['->' <data type>] '{' <assembly code> '}', where param is ['!'] \<name> [<data type>]
    NAME = "MACRO"

    @classmethod
    def register(cls):
        from bytecodemanipulation.assembler.Parser import Parser

        Parser.register(cls)

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
            raise RuntimeError

    class AnyDataType(AbstractDataType):
        IDENTIFIER = "ANY"

        def is_match(
            self,
            arg: "MacroAssembly.MacroArg",
            arg_accessor: AbstractAccessExpression | CompoundExpression,
        ) -> bool:
            return True

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
    def _try_parse_arg_data_type(cls, parser: "Parser") -> AbstractDataType | None:
        if identifier := parser.try_inspect(IdentifierToken):
            if identifier.text == "CODE_BLOCK":
                parser.consume(identifier)
                inst = cls.CodeBlockDataType()
                return inst

            elif identifier.text == "VARIABLE_ARG":
                parser.consume(identifier)
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
                parser.consume(identifier)
                inst = cls.VariableDataType()
                return inst

            elif identifier.text == "ANY":
                parser.consume(identifier)
                return cls.AnyDataType()

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

        if parser.try_consume(SpecialToken("-")):
            parser.consume(SpecialToken(">"), err_arg=scope)

            return_type = cls._try_parse_arg_data_type(parser)
        else:
            return_type = None

        body = parser.parse_body(scope=scope)

        return cls(
            name,
            args,
            body,
            allow_assembly_instr,
            scope_path=scope.scope_path.copy(),
            module_path=scope.module_file,
            return_type=return_type,
        )

    def __init__(
        self,
        name: typing.List[IdentifierToken],
        args: typing.List[MacroArg],
        body: CompoundExpression,
        allow_assembly_instr=False,
        scope_path: typing.List[str] = None,
        module_path: str = None,
        return_type=None,
    ):
        self.name = name
        self.args = args
        self.body = body
        self.allow_assembly_instr = allow_assembly_instr
        self.scope_path = scope_path or []
        self.module_path = module_path
        self.return_type = return_type

    def __repr__(self):
        return f"MACRO:{'ASSEMBLY' if self.allow_assembly_instr else ''}:'{':'.join(map(lambda e: e.text, self.name))}'({', '.join(map(repr, self.args))}) {{{repr(self.body)}}}"

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.name == other.name
            and self.args == other.args
            and self.body == other.body
            and self.allow_assembly_instr == other.allow_assembly_instr
            and self.return_type == other.return_type
        )

    def copy(self) -> "MacroAssembly":
        return type(self)(
            self.name.copy(),
            [arg.copy() for arg in self.args],
            self.body.copy(),
            self.allow_assembly_instr,
            return_type=self.return_type,
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
        end_target = scope.scope_name_generator("macro_end")
        requires_none_load = (
            self.return_type is not None
            and not inner_bytecode[-1].has_unconditional_jump()
            and inner_bytecode[-1].opcode != Opcodes.RETURN_VALUE
        )

        for instr in inner_bytecode:
            bytecode.append(instr)

            if instr.opcode in (
                Opcodes.MACRO_LOAD_PARAMETER,
                Opcodes.MACRO_PARAMETER_EXPANSION,
            ):
                if instr.arg_value not in arg_decl_lookup:
                    raise throw_positioned_syntax_error(
                        scope,
                        self.name,
                        f"macro name {instr.arg_value} not found in scope",
                    )

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

            elif instr.opcode == Opcodes.MACRO_STORE_PARAMETER:
                if instr.arg_value not in arg_decl_lookup:
                    raise throw_positioned_syntax_error(
                        scope,
                        self.name,
                        f"macro name {instr.arg_value} not found in scope",
                    )

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

            elif instr.opcode == Opcodes.MACRO_RETURN_VALUE:
                if self.return_type is None:
                    raise SyntaxError(
                        "'MACRO_RETURN' only allowed in assembly if return type declared!"
                    )

                instr.change_opcode(Opcodes.JUMP_ABSOLUTE, JumpToLabel(end_target))

        if requires_none_load:
            bytecode.append(Instruction(function, -1, Opcodes.LOAD_CONST, None))

        bytecode.append(Instruction(function, -1, Opcodes.BYTECODE_LABEL, end_target))

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
        def __init__(
            self, function: typing.Callable, scoped_names: typing.List[str] = None
        ):
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
                    else instr.copy(owner=function)
                    .change_opcode(Opcodes.POP_TOP)
                    .insert_after(
                        Instruction(
                            function,
                            -1,
                            Opcodes.JUMP_ABSOLUTE,
                            JumpToLabel(macro_exit_label),
                        )
                    )
                )
                if not instr.has_local() or instr.arg_value not in self.scoped_names
                else instr.copy(owner=function).change_opcode(
                    LOCAL_TO_DEREF_OPCODES[instr.opcode]
                )
                for instr in self.function.instructions
            ] + [Instruction(function, -1, Opcodes.BYTECODE_LABEL, macro_exit_label)]
