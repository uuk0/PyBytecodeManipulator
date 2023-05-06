import typing

from bytecodemanipulation.assembler.Lexer import SpecialToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import AbstractAssemblyInstruction
from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.data.shared.expressions.CompoundExpression import CompoundExpression
from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class IFAssembly(AbstractAssemblyInstruction):
    # IF <expression> ['\'' <label name> '\''] '{' <body> '}'
    NAME = "IF"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "IFAssembly":
        source = parser.try_parse_data_source(
            allow_primitives=True, include_bracket=False, scope=scope
        )

        if source is None:
            raise throw_positioned_syntax_error(
                scope, parser.try_inspect(), "expected <expression>"
            )

        if parser.try_consume(SpecialToken("'")):
            label_name = parser.consume(IdentifierToken)
            if not parser.try_consume(SpecialToken("'")):
                raise throw_positioned_syntax_error(
                    scope, parser.try_inspect(), "expected '"
                )
        else:
            label_name = None

        body = parser.parse_body(scope=scope)

        return cls(
            source,
            body,
            label_name,
        )

    def __init__(
        self,
        source: AbstractSourceExpression,
        body: CompoundExpression,
        label_name: IdentifierToken | str | None = None,
    ):
        self.source = source
        self.body = body
        self.label_name = (
            label_name
            if not isinstance(label_name, str)
            else IdentifierToken(label_name)
        )

    def copy(self):
        return type(self)(self.source.copy(), self.body.copy(), self.label_name)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.body == other.body
            and self.label_name == other.label_name
        )

    def __repr__(self):
        c = "'"
        return f"IF({self.source}{'' if self.label_name is None else ', label='+c+self.label_name.text+c}) -> {{{self.body}}}"

    def emit_bytecodes(self, function: MutableFunction, scope: ParsingScope):

        if self.label_name is None:
            end = Instruction(function, -1, "NOP")
        else:
            end = Instruction(
                function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text + "_END"
            )

        return (
            (
                []
                if self.label_name is None
                else [
                    Instruction(
                        function,
                        -1,
                        Opcodes.BYTECODE_LABEL,
                        self.label_name.text + "_HEAD",
                    )
                ]
            )
            + self.source.emit_bytecodes(function, scope)
            + [Instruction(function, -1, "POP_JUMP_IF_FALSE", end)]
            + (
                []
                if self.label_name is None
                else [
                    Instruction(
                        function, -1, Opcodes.BYTECODE_LABEL, self.label_name.text
                    )
                ]
            )
            + self.body.emit_bytecodes(function, scope)
            + [end]
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
            self, (self.source.visit_parts(visitor), self.body.visit_parts(visitor))
        )

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, (self.body.visit_assembly_instructions(visitor),))

    def get_labels(self) -> typing.Set[str]:
        return (
            set()
            if self.label_name is None
            else {
                self.label_name.text,
                self.label_name.text + "_END",
                self.label_name.text + "_HEAD",
            }
        ) | self.body.get_labels()
