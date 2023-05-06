import typing

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import AbstractAssemblyInstruction
from bytecodemanipulation.data.shared.expressions.CompoundExpression import CompoundExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.data.shared.instructions.CallAssembly import AbstractCallAssembly
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.util import LambdaInstructionWalker


@Parser.register
class FunctionDefinitionAssembly(AbstractAssemblyInstruction):
    # DEF [<func name>] ['<' ['!'] <bound variables\> '>'] '(' <signature> ')' ['->' <target>] '{' <body> '}'
    NAME = "DEF"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "FunctionDefinitionAssembly":
        func_name = parser.try_consume(IdentifierToken)
        bound_variables: typing.List[typing.Tuple[typing.Callable[[ParsingScope], str], bool]] = []
        args = []

        if parser.try_consume(SpecialToken("<")):
            is_static = bool(parser.try_consume(SpecialToken("!")))

            expr = parser.try_parse_identifier_like()

            if expr:
                bound_variables.append((expr, is_static))

                while True:
                    if not parser.try_consume(SpecialToken(",")) or not (
                        expr := parser.try_parse_identifier_like()
                    ):
                        break

                    bound_variables.append((expr, is_static))

            parser.consume(SpecialToken(">"), err_arg=scope)

        parser.consume(SpecialToken("("), err_arg=scope)

        while parser.try_inspect() != SpecialToken(")"):
            arg = None

            star = parser.try_consume(SpecialToken("*"))
            star_star = parser.try_consume(SpecialToken("*"))
            identifier = parser.try_consume(IdentifierToken)

            if not identifier:
                if star:
                    raise throw_positioned_syntax_error(
                        scope,
                        [star, star_star],
                        "Expected <expression> after '*'" if not star_star else "Expected <expression> after '**'"
                    )

                break

            if not star:
                if parser.try_consume(SpecialToken("=")):
                    default_value = parser.try_parse_data_source(
                        allow_primitives=True, include_bracket=False, allow_op=True
                    )

                    if default_value is None:
                        raise SyntaxError

                    arg = AbstractCallAssembly.IMPLEMENTATION.KwArg(identifier, default_value)

            if not arg:
                if star_star:
                    arg = AbstractCallAssembly.IMPLEMENTATION.KwArgStar(identifier)
                elif star:
                    arg = AbstractCallAssembly.IMPLEMENTATION.StarArg(identifier)
                else:
                    arg = AbstractCallAssembly.IMPLEMENTATION.Arg(identifier)

            args.append(arg)

            if not parser.try_consume(SpecialToken(",")):
                break

        parser.consume(SpecialToken(")"))

        if expr := parser.try_consume(SpecialToken("<")):
            raise throw_positioned_syntax_error(
                scope,
                expr,
                "Respect ordering (got 'args' before 'captured'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }",
            )

        if parser.try_consume(SpecialToken("-")) and parser.try_consume(
            SpecialToken(">")
        ):
            target = parser.try_consume_access_to_value(scope=scope)
        else:
            target = None

        body = parser.parse_body(scope=scope)

        if expr := parser.try_consume(SpecialToken("-")):
            raise throw_positioned_syntax_error(
                scope,
                expr,
                "Respect ordering (got 'code' before 'target'): DEF ['name'] ['captured'] ('args') [-> 'target'] { code }",
            )

        return cls(func_name, bound_variables, args, body, target)

    def __init__(
        self,
        func_name: IdentifierToken | str | None,
        bound_variables: typing.List[typing.Tuple[IdentifierToken | str, bool] | str],
        args: typing.List[AbstractCallAssembly.IMPLEMENTATION.IArg],
        body: CompoundExpression,
        target: AbstractAccessExpression | None = None,
    ):
        self.func_name = (
            func_name if not isinstance(func_name, str) else IdentifierToken(func_name)
        )
        self.bound_variables: typing.List[typing.Tuple[typing.Callable[[ParsingScope], str], bool]] = []
        # var if isinstance(var, IdentifierToken) else IdentifierToken(var) for var in bound_variables]

        def _create_lazy(name: str):
            return lambda scope: name

        for element in bound_variables:
            if isinstance(element, str):
                self.bound_variables.append(
                    (
                        _create_lazy(element.removeprefix("!")),
                        element.startswith("!"),
                    )
                )
            elif isinstance(element, tuple):
                token, is_static = element

                if isinstance(token, str):
                    self.bound_variables.append((_create_lazy(token), is_static))
                else:
                    self.bound_variables.append(element)
            else:
                raise ValueError(element)

        self.args = args
        self.body = body
        self.target = target

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
                [arg.visit_parts(visitor) for arg in self.args],
                self.body.visit_parts(visitor),
                self.target.visit_parts(visitor) if self.target else None,
            ),
        )

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.func_name == other.func_name
            and len(self.bound_variables) == len(other.bound_variables)
            and all((a[0](None) == b[0](None) and a[1] == b[1] for a, b in zip(self.bound_variables, other.bound_variables)))
            and self.args == other.args
            and self.body == other.body
            and self.target == other.target
        )

    def __repr__(self):
        return f"DEF({self.func_name.text}<{repr([(name[0](None), name[1]) for name in self.bound_variables])[1:-1]}>({repr(self.args)[1:-1]}){'-> ' + repr(self.target) if self.target else ''} {{ {self.body} }})"

    def copy(self) -> "FunctionDefinitionAssembly":
        return FunctionDefinitionAssembly(
            self.func_name,
            self.bound_variables.copy(),
            [arg.copy() for arg in self.args],
            self.body.copy(),
            self.target.copy() if self.target else None,
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        flags = 0
        bytecode = []

        inner_labels = self.body.collect_label_info()
        label_targets = {}

        inner_scope = scope.copy()

        if self.bound_variables:
            if any(map(lambda e: e[1], self.bound_variables)):
                raise NotImplementedError("Static variables")

            names = [e[0](scope) for e in self.bound_variables]
            s = {}
            exec(f"{' = '.join(names)} = None\nresult = lambda: ({', '.join(names)})", s)
            tar = s["result"]
        else:
            tar = lambda: None

        target = MutableFunction(tar)
        inner_bytecode = []

        if self.bound_variables:
            for name, is_static in self.bound_variables:
                print(name, name(scope), is_static)
                inner_bytecode += [
                    Instruction(target, -1, Opcodes.LOAD_DEREF, name(scope) + "%inner"),
                    Instruction(target, -1, Opcodes.STORE_DEREF, name(scope)),
                ]

        inner_bytecode += self.body.emit_bytecodes(target, inner_scope)
        inner_bytecode[-1].next_instruction = target.instructions[0]

        for i, instr in enumerate(inner_bytecode[:-1]):
            instr.next_instruction = inner_bytecode[i + 1]

        def walk_label(instruction: Instruction):
            if instruction.opcode == Opcodes.BYTECODE_LABEL:
                # print(instruction, instruction.next_instruction)
                label_targets[instruction.arg_value] = instruction.next_instruction if instruction.next_instruction is not None else instruction
                instruction.change_opcode(Opcodes.NOP, update_next=False)

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(walk_label))

        def resolve_jump_to_label(ins: Instruction):
            if ins.has_jump() and isinstance(ins.arg_value, JumpToLabel):
                ins.change_arg_value(label_targets[ins.arg_value.name])

        inner_bytecode[0].apply_visitor(LambdaInstructionWalker(resolve_jump_to_label))

        target.assemble_instructions_from_tree(inner_bytecode[0])
        del inner_bytecode

        has_kwarg = False
        for arg in self.args:
            if isinstance(arg, AbstractCallAssembly.IMPLEMENTATION.KwArg):
                has_kwarg = True
                break

        if has_kwarg:
            flags |= 0x02
            raise NotImplementedError("Kwarg defaults")

        if self.bound_variables:
            if any(map(lambda e: e[1], self.bound_variables)):
                raise NotImplementedError("Static variables")

            flags |= 0x08

            for name, is_static in self.bound_variables:
                bytecode += [
                    Instruction(function, -1, Opcodes.LOAD_FAST, name(scope)),
                    Instruction(function, -1, Opcodes.STORE_DEREF, name(scope)+"%inner"),
                ]

            bytecode += [
                Instruction(function, -1, Opcodes.LOAD_CLOSURE, name(scope)+"%inner")
                for name, is_static in self.bound_variables
            ]
            bytecode.append(
                Instruction(function, -1, Opcodes.BUILD_TUPLE, arg=len(self.bound_variables))
            )

        target.argument_count = len(self.args)
        code_object = target.create_code_obj()

        bytecode += [
            Instruction(function, -1, "LOAD_CONST", code_object),
            Instruction(
                function,
                -1,
                "LOAD_CONST",
                self.func_name.text if self.func_name else "<lambda>",
            ),
            Instruction(function, -1, "MAKE_FUNCTION", arg=flags),
        ]

        if self.target:
            bytecode += self.target.emit_store_bytecodes(function, scope)
        else:
            bytecode += [
                Instruction(function, -1, Opcodes.STORE_FAST, self.func_name.text),
            ]

        return bytecode
