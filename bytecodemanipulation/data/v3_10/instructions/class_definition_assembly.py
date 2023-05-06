import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)
from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import (
    ConstantAccessExpression,
)
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class ClassDefinitionAssembly(AbstractAssemblyInstruction):
    # CLASS <name> ['(' [<parent> {',' <parent>}] ')'] '{' ... '}'
    NAME = "CLASS"

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "ClassDefinitionAssembly":
        name_token = parser.consume(IdentifierToken, err_arg=scope)

        parents = []

        if parser.try_consume(SpecialToken("(")):
            if parent := parser.try_consume_access_to_value():
                parents.append(parent)

                while parser.try_consume(SpecialToken(",")):
                    if parser[0] == SpecialToken(")"):
                        break

                    parent = parser.try_consume_access_to_value()
                    if parent is None:
                        raise throw_positioned_syntax_error(
                            scope,
                            parser[0],
                            "Expected <expression>",
                        )
                    parents.append(parent)

            if not parser.try_consume(SpecialToken(")")):
                raise throw_positioned_syntax_error(scope, parser[0], "Expected ')'")

        if not parents:
            parents = [ConstantAccessExpression(object)]

        code_block = parser.parse_body(namespace_part=name_token.text, scope=scope)
        return cls(
            name_token,
            parents,
            code_block,
        )

    def __init__(
        self,
        name_token: IdentifierToken,
        parents: typing.List[AbstractAccessExpression],
        code_block: CompoundExpression,
    ):
        self.name_token = name_token
        self.parents = parents
        self.code_block = code_block

    def __repr__(self):
        return f"ClassAssembly::'{self.name_token.text}'({','.join(map(repr, self.parents))}){{{self.code_block}}}"

    def copy(self):
        return ClassDefinitionAssembly(
            self.name_token,
            [parent.copy() for parent in self.parents],
            self.code_block.copy(),
        )

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.name_token == other.name_token
            and self.parents == other.parents
            and self.code_block == other.code_block
        )

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        inner_scope = scope.copy(sub_scope_name=self.name_token.text)

        target = MutableFunction(lambda: None)

        inner_bytecode = [
            Instruction(target, -1, Opcodes.LOAD_NAME, "__name__"),
            Instruction(target, -1, Opcodes.STORE_NAME, "__module__"),
            Instruction(target, -1, Opcodes.LOAD_CONST, self.name_token.text),
            Instruction(target, -1, Opcodes.STORE_NAME, "__qualname__"),
        ]

        raw_inner_code = self.code_block.emit_bytecodes(target, inner_scope)

        for instr in raw_inner_code:
            if instr.opcode == Opcodes.LOAD_FAST:
                instr.change_opcode(Opcodes.LOAD_NAME, arg_value=instr.arg_value)
            elif instr.opcode == Opcodes.STORE_FAST:
                instr.change_opcode(Opcodes.STORE_NAME, arg_value=instr.arg_value)
            elif instr.opcode == Opcodes.DELETE_FAST:
                instr.change_opcode(Opcodes.DELETE_NAME, arg_value=instr.arg_value)

        inner_bytecode += raw_inner_code

        if inner_bytecode:
            inner_bytecode[-1].next_instruction = target.instructions[0]

        for i, instr in enumerate(inner_bytecode[:-1]):
            instr.next_instruction = inner_bytecode[i + 1]

        target.assemble_instructions_from_tree(inner_bytecode[0])
        target.reassign_to_function()

        code_obj = target.target.__code__

        bytecode = [
            Instruction(function, -1, Opcodes.LOAD_BUILD_CLASS),
            Instruction(function, -1, Opcodes.LOAD_CONST, code_obj),
            Instruction(function, -1, Opcodes.LOAD_CONST, self.name_token.text),
            Instruction(function, -1, Opcodes.MAKE_FUNCTION, arg=0),
            Instruction(function, -1, Opcodes.LOAD_CONST, self.name_token.text),
        ]

        for parent in self.parents:
            bytecode += parent.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2 + len(self.parents)),
            Instruction(function, -1, Opcodes.STORE_FAST, self.name_token.text),
        ]
        return bytecode
