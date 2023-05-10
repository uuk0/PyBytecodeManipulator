import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.OpAssembly import OpcodeBaseOperator
from bytecodemanipulation.MutableFunction import MutableFunction

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.OpAssembly import (
    AbstractOpAssembly,
    AbstractOperator,
)
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.Opcodes import Opcodes


class NandOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        label_name = scope.scope_name_generator("and_skip_second")

        bytecode = lhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.DUP_TOP),
            Instruction(
                function, -1, Opcodes.POP_JUMP_IF_FALSE, JumpToLabel(label_name)
            ),
            Instruction(function, -1, Opcodes.POP_TOP),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.BYTECODE_LABEL, label_name),
            Instruction(function, -1, Opcodes.UNARY_NOT, bool),
        ]
        return bytecode


class AndOperator(NandOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        return super().emit_bytecodes(function, scope, lhs, rhs) + [
            Instruction(function, -1, Opcodes.UNARY_NOT, bool)
        ]


class NorOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        label_name = scope.scope_name_generator("or_skip_second")

        bytecode = lhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.DUP_TOP),
            Instruction(
                function, -1, Opcodes.POP_JUMP_IF_TRUE, JumpToLabel(label_name)
            ),
            Instruction(function, -1, Opcodes.POP_TOP),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.BYTECODE_LABEL, label_name),
            Instruction(function, -1, Opcodes.UNARY_NOT, bool),
        ]
        return bytecode


class OrOperator(NorOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        return super().emit_bytecodes(function, scope, lhs, rhs) + [
            Instruction(function, -1, Opcodes.UNARY_NOT, bool)
        ]


class XOROperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = lhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.UNARY_NOT),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.UNARY_NOT),
            Instruction(function, -1, Opcodes.COMPARE_OP, arg=3),
        ]
        return bytecode


class XNOROperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = lhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.UNARY_NOT),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.UNARY_NOT),
            Instruction(function, -1, Opcodes.COMPARE_OP, arg=2),
        ]
        return bytecode


class WalrusOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.DUP_TOP),
        ]
        bytecode += lhs.emit_store_bytecodes(function, scope)
        return bytecode


class InverseWalrusOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = lhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(function, -1, Opcodes.DUP_TOP),
        ]
        bytecode += rhs.emit_store_bytecodes(function, scope)
        return bytecode


class InstanceOfChecker(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = lhs.emit_bytecodes(function, scope) + rhs.emit_bytecodes(
            function, scope
        )
        bytecode += [
            Instruction(function, -1, Opcodes.LOAD_CONST, isinstance),
            Instruction(function, -1, Opcodes.ROT_THREE),
            Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2),
        ]
        return bytecode


class SubclassOfChecker(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = lhs.emit_bytecodes(function, scope) + rhs.emit_bytecodes(
            function, scope
        )
        bytecode += [
            Instruction(function, -1, Opcodes.LOAD_CONST, issubclass),
            Instruction(function, -1, Opcodes.ROT_THREE),
            Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2),
        ]
        return bytecode


class HasattrChecker(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = lhs.emit_bytecodes(function, scope) + rhs.emit_bytecodes(
            function, scope
        )
        bytecode += [
            Instruction(function, -1, Opcodes.LOAD_CONST, hasattr),
            Instruction(function, -1, Opcodes.ROT_THREE),
            Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2),
        ]
        return bytecode


class SumOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression
    ) -> typing.List[Instruction]:
        if len(parameters) == 0:
            raise SyntaxError("expected at least one parameter")

        bytecode = parameters[0].emit_bytecodes(function, scope)

        for param in parameters[1:]:
            bytecode += param.emit_bytecodes(function, scope)
            bytecode.append(Instruction(function, -1, Opcodes.BINARY_ADD))

        return bytecode


class ProdOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression
    ) -> typing.List[Instruction]:
        if len(parameters) == 0:
            raise SyntaxError("expected at least one parameter")

        bytecode = parameters[0].emit_bytecodes(function, scope)

        for param in parameters[1:]:
            bytecode += param.emit_bytecodes(function, scope)
            bytecode.append(Instruction(function, -1, Opcodes.BINARY_MULTIPLY))

        return bytecode


class AvgOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression
    ) -> typing.List[Instruction]:
        if len(parameters) == 0:
            raise SyntaxError("expected at least one parameter")

        bytecode = parameters[0].emit_bytecodes(function, scope)

        for param in parameters[1:]:
            bytecode += param.emit_bytecodes(function, scope)
            bytecode.append(Instruction(function, -1, Opcodes.BINARY_ADD))

        bytecode += [
            Instruction(function, -1, Opcodes.LOAD_CONST, len(parameters)),
            Instruction(function, -1, Opcodes.BINARY_TRUE_DIVIDE),
        ]

        return bytecode


class AvgIOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression
    ) -> typing.List[Instruction]:
        if len(parameters) == 0:
            raise SyntaxError("expected at least one parameter")

        bytecode = parameters[0].emit_bytecodes(function, scope)

        for param in parameters[1:]:
            bytecode += param.emit_bytecodes(function, scope)
            bytecode.append(Instruction(function, -1, Opcodes.BINARY_ADD))

        bytecode += [
            Instruction(function, -1, Opcodes.LOAD_CONST, len(parameters)),
            Instruction(function, -1, Opcodes.BINARY_FLOOR_DIVIDE),
        ]

        return bytecode


@Parser.register
class OpAssembly(AbstractOpAssembly):
    BINARY_OPS = {
        "+": OpcodeBaseOperator(Opcodes.BINARY_ADD),
        "-": OpcodeBaseOperator(Opcodes.BINARY_SUBTRACT),
        "*": OpcodeBaseOperator(Opcodes.BINARY_MULTIPLY),
        "/": OpcodeBaseOperator(Opcodes.BINARY_TRUE_DIVIDE),
        "//": OpcodeBaseOperator(Opcodes.BINARY_FLOOR_DIVIDE),
        "**": OpcodeBaseOperator(Opcodes.BINARY_MULTIPLY),
        "%": OpcodeBaseOperator(Opcodes.BINARY_MODULO),
        "&": OpcodeBaseOperator(Opcodes.BINARY_AND),
        "|": OpcodeBaseOperator(Opcodes.BINARY_OR),
        "^": OpcodeBaseOperator(Opcodes.BINARY_XOR),
        ">>": OpcodeBaseOperator(Opcodes.BINARY_RSHIFT),
        "<<": OpcodeBaseOperator(Opcodes.BINARY_LSHIFT),
        "@": OpcodeBaseOperator(Opcodes.BINARY_MATRIX_MULTIPLY),
        "is": OpcodeBaseOperator((Opcodes.IS_OP, 0)),
        "!is": OpcodeBaseOperator((Opcodes.IS_OP, 1)),
        "in": OpcodeBaseOperator((Opcodes.CONTAINS_OP, 0)),
        "!in": OpcodeBaseOperator((Opcodes.CONTAINS_OP, 1)),
        "<": OpcodeBaseOperator((Opcodes.COMPARE_OP, 0)),
        "<=": OpcodeBaseOperator((Opcodes.COMPARE_OP, 1)),
        "==": OpcodeBaseOperator((Opcodes.COMPARE_OP, 2)),
        "!=": OpcodeBaseOperator((Opcodes.COMPARE_OP, 3)),
        ">": OpcodeBaseOperator((Opcodes.COMPARE_OP, 4)),
        ">=": OpcodeBaseOperator((Opcodes.COMPARE_OP, 5)),
        "xor": XOROperator(),
        "!xor": XNOROperator(),
        "xnor": XNOROperator(),
        ":=": WalrusOperator(),
        "=:": InverseWalrusOperator(),
        "isinstance": InstanceOfChecker(),
        "instanceof": InstanceOfChecker(),
        "issubclass": SubclassOfChecker(),
        "subclassof": SubclassOfChecker(),
        "hasattr": HasattrChecker(),
        "and": AndOperator(),
        "!and": NandOperator(),
        "nand": NandOperator(),
        "or": OrOperator(),
        "!or": NorOperator(),
        "nor": NorOperator(),
    }

    SINGLE_OPS = {
        "-": OpcodeBaseOperator(Opcodes.UNARY_NEGATIVE),
        "+": OpcodeBaseOperator(Opcodes.UNARY_POSITIVE),
        "~": OpcodeBaseOperator(Opcodes.UNARY_INVERT),
        "not": OpcodeBaseOperator(Opcodes.UNARY_NOT),
        "!": OpcodeBaseOperator(Opcodes.UNARY_NOT),
    }

    PREFIX_OPERATORS = {
        "sum": (SumOperator(), None, True, True),
        "prod": (ProdOperator(), None, True, True),
        "avg": (AvgOperator(), None, True, True),
        "avgi": (AvgIOperator(), None, True, True),
    }

    # todo: inplace variants
