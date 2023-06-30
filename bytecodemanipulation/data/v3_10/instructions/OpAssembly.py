import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import JumpToLabel
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.data.shared.instructions.OpAssembly import OpcodeBaseOperator
from bytecodemanipulation.MutableFunction import MutableFunction

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.OpAssembly import (
    AbstractOpAssembly,
    AbstractOperator,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


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
            Instruction(Opcodes.DUP_TOP),
            Instruction(
                Opcodes.POP_JUMP_IF_FALSE, JumpToLabel(label_name)
            ),
            Instruction(Opcodes.POP_TOP),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(Opcodes.BYTECODE_LABEL, label_name),
            Instruction(Opcodes.UNARY_NOT, bool),
        ]
        return bytecode

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        if not lhs.evaluate_static_value(scope):
            return True

        return not rhs.evaluate_static_value(scope)


class AndOperator(NandOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        return super().emit_bytecodes(function, scope, lhs, rhs) + [
            Instruction(Opcodes.UNARY_NOT, bool)
        ]

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        if not lhs.evaluate_static_value(scope):
            return False

        return rhs.evaluate_static_value(scope)


class AndEvalOperator(NandOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        inner_label = scope.scope_name_generator("and_eval_swap_skip")

        return lhs.emit_bytecodes(function, scope) + rhs.emit_bytecodes(function, scope) + [
            Instruction(Opcodes.DUP_TOP),
            Instruction(Opcodes.POP_JUMP_IF_TRUE, JumpToLabel(inner_label)),
            Instruction(Opcodes.ROT_TWO),
            Instruction(Opcodes.BYTECODE_LABEL, inner_label),
            Instruction(Opcodes.POP_TOP),
        ]

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        lhs = lhs.evaluate_static_value(scope)
        rhs = rhs.evaluate_static_value(scope)

        return bool(lhs and rhs)


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
            Instruction(Opcodes.DUP_TOP),
            Instruction(
                Opcodes.POP_JUMP_IF_TRUE, JumpToLabel(label_name)
            ),
            Instruction(Opcodes.POP_TOP),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(Opcodes.BYTECODE_LABEL, label_name),
            Instruction(Opcodes.UNARY_NOT, bool),
        ]
        return bytecode

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        if lhs.evaluate_static_value(scope):
            return False

        return not rhs.evaluate_static_value(scope)


class OrOperator(NorOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        return super().emit_bytecodes(function, scope, lhs, rhs) + [
            Instruction(Opcodes.UNARY_NOT, bool)
        ]

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        if lhs.evaluate_static_value(scope):
            return True

        return rhs.evaluate_static_value(scope)


class OrEvalOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        lhs: AbstractSourceExpression,
        rhs: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        inner_label = scope.scope_name_generator("or_eval_swap_skip")

        return lhs.emit_bytecodes(function, scope) + rhs.emit_bytecodes(function, scope) + [
            Instruction(Opcodes.DUP_TOP),
            Instruction(Opcodes.POP_JUMP_IF_FALSE, JumpToLabel(inner_label)),
            Instruction(Opcodes.ROT_TWO),
            Instruction(Opcodes.BYTECODE_LABEL, inner_label),
            Instruction(Opcodes.POP_TOP),
        ]

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        lhs = lhs.evaluate_static_value(scope)
        rhs = rhs.evaluate_static_value(scope)

        return bool(lhs or rhs)


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
            Instruction(Opcodes.UNARY_NOT),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(Opcodes.UNARY_NOT),
            Instruction(Opcodes.COMPARE_NEQ),
        ]
        return bytecode

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        lhs = lhs.evaluate_static_value(scope)
        rhs = rhs.evaluate_static_value(scope)

        return lhs != rhs


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
            Instruction(Opcodes.UNARY_NOT),
        ]
        bytecode += rhs.emit_bytecodes(function, scope)
        bytecode += [
            Instruction(Opcodes.UNARY_NOT),
            Instruction(Opcodes.COMPARE_EQ),
        ]
        return bytecode

    def evaluate_static_value(self, scope: ParsingScope, lhs: AbstractSourceExpression, rhs: AbstractSourceExpression):
        lhs = lhs.evaluate_static_value(scope)
        rhs = rhs.evaluate_static_value(scope)

        return lhs == rhs


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
            Instruction(Opcodes.DUP_TOP),
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
            Instruction(Opcodes.DUP_TOP),
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
            Instruction(Opcodes.LOAD_CONST, isinstance),
            Instruction(Opcodes.ROT_THREE),
            Instruction(Opcodes.CALL_FUNCTION, arg=2),
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
            Instruction(Opcodes.LOAD_CONST, issubclass),
            Instruction(Opcodes.ROT_THREE),
            Instruction(Opcodes.CALL_FUNCTION, arg=2),
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
            Instruction(Opcodes.LOAD_CONST, hasattr),
            Instruction(Opcodes.ROT_THREE),
            Instruction(Opcodes.CALL_FUNCTION, arg=2),
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
            bytecode.append(Instruction(Opcodes.BINARY_ADD))

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
            bytecode.append(Instruction(Opcodes.BINARY_MULTIPLY))

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
            bytecode.append(Instruction(Opcodes.BINARY_ADD))

        bytecode += [
            Instruction(Opcodes.LOAD_CONST, len(parameters)),
            Instruction(Opcodes.BINARY_TRUE_DIVIDE),
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
            bytecode.append(Instruction(Opcodes.BINARY_ADD))

        bytecode += [
            Instruction(Opcodes.LOAD_CONST, len(parameters)),
            Instruction(Opcodes.BINARY_FLOOR_DIVIDE),
        ]

        return bytecode


class TupleOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = []

        for param in parameters:
            bytecode += param.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(Opcodes.BUILD_TUPLE, arg=len(parameters)),
        ]

        return bytecode

    def evaluate_static_value(self, scope: ParsingScope, *parameters: AbstractSourceExpression):
        return tuple(
            [
                param.evaluate_static_value(scope)
                for param in parameters
            ]
        )


class ListOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = []

        for param in parameters:
            bytecode += param.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(Opcodes.BUILD_LIST, arg=len(parameters)),
        ]

        return bytecode


class SetOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        bytecode = []

        for param in parameters:
            bytecode += param.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(Opcodes.BUILD_SET, arg=len(parameters)),
        ]

        return bytecode


class DictOperator(AbstractOperator):
    def emit_bytecodes(
        self,
        function: MutableFunction,
        scope: ParsingScope,
        *parameters: AbstractSourceExpression,
    ) -> typing.List[Instruction]:
        if len(parameters) % 2 != 0:
            raise throw_positioned_error(
                scope,
                sum([list(param.get_tokens()) for param in parameters], []),
                "expected even arg count for dict build",
            )

        bytecode = []

        for param in parameters:
            bytecode += param.emit_bytecodes(
                function,
                scope,
            )

        bytecode += [
            Instruction(Opcodes.BUILD_MAP, arg=len(parameters) // 2),
        ]

        return bytecode


@Parser.register
class OpAssembly(AbstractOpAssembly):
    BINARY_OPS = {
        "+": OpcodeBaseOperator(Opcodes.BINARY_ADD, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) + x[1].evaluate_static_value(scope)),
        "-": OpcodeBaseOperator(Opcodes.BINARY_SUBTRACT, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) - x[1].evaluate_static_value(scope)),
        "*": OpcodeBaseOperator(Opcodes.BINARY_MULTIPLY, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) * x[1].evaluate_static_value(scope)),
        "/": OpcodeBaseOperator(Opcodes.BINARY_TRUE_DIVIDE, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) / x[1].evaluate_static_value(scope)),
        "//": OpcodeBaseOperator(Opcodes.BINARY_FLOOR_DIVIDE, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) // x[1].evaluate_static_value(scope)),
        "**": OpcodeBaseOperator(Opcodes.BINARY_POWER, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) ** x[1].evaluate_static_value(scope)),
        "%": OpcodeBaseOperator(Opcodes.BINARY_MODULO, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) % x[1].evaluate_static_value(scope)),
        "&": OpcodeBaseOperator(Opcodes.BINARY_AND, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) & x[1].evaluate_static_value(scope)),
        "|": OpcodeBaseOperator(Opcodes.BINARY_OR, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) | x[1].evaluate_static_value(scope)),
        "^": OpcodeBaseOperator(Opcodes.BINARY_XOR, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) ^ x[1].evaluate_static_value(scope)),
        ">>": OpcodeBaseOperator(Opcodes.BINARY_RSHIFT, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) >> x[1].evaluate_static_value(scope)),
        "<<": OpcodeBaseOperator(Opcodes.BINARY_LSHIFT, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) << x[1].evaluate_static_value(scope)),
        "@": OpcodeBaseOperator(Opcodes.BINARY_MATRIX_MULTIPLY, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) @ x[1].evaluate_static_value(scope)),
        "is": OpcodeBaseOperator((Opcodes.IS_OP, 0), static_eval=lambda scope, x: x[0].evaluate_static_value(scope) is x[1].evaluate_static_value(scope)),
        "!is": OpcodeBaseOperator((Opcodes.IS_OP, 1), static_eval=lambda scope, x: x[0].evaluate_static_value(scope) is not x[1].evaluate_static_value(scope)),
        "in": OpcodeBaseOperator((Opcodes.CONTAINS_OP, 0), static_eval=lambda scope, x: x[0].evaluate_static_value(scope) in x[1].evaluate_static_value(scope)),
        "!in": OpcodeBaseOperator((Opcodes.CONTAINS_OP, 1), static_eval=lambda scope, x: x[0].evaluate_static_value(scope) not in x[1].evaluate_static_value(scope)),
        "<": OpcodeBaseOperator(Opcodes.COMPARE_LT, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) < x[1].evaluate_static_value(scope)),
        "<=": OpcodeBaseOperator(Opcodes.COMPARE_LE, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) <= x[1].evaluate_static_value(scope)),
        "==": OpcodeBaseOperator(Opcodes.COMPARE_EQ, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) == x[1].evaluate_static_value(scope)),
        "!=": OpcodeBaseOperator(Opcodes.COMPARE_NEQ, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) != x[1].evaluate_static_value(scope)),
        ">": OpcodeBaseOperator(Opcodes.COMPARE_GT, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) > x[1].evaluate_static_value(scope)),
        ">=": OpcodeBaseOperator(Opcodes.COMPARE_GE, static_eval=lambda scope, x: x[0].evaluate_static_value(scope) >= x[1].evaluate_static_value(scope)),
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
        "andeval": AndEvalOperator(),
        "!and": NandOperator(),
        "nand": NandOperator(),
        "or": OrOperator(),
        "oreval": OrEvalOperator(),
        "!or": NorOperator(),
        "nor": NorOperator(),
    }

    SINGLE_OPS = {
        "-": OpcodeBaseOperator(Opcodes.UNARY_NEGATIVE, static_eval=lambda scope, x: -x[0].evaluate_static_value(scope)),
        "+": OpcodeBaseOperator(Opcodes.UNARY_POSITIVE, static_eval=lambda scope, x: +x[0].evaluate_static_value(scope)),
        "~": OpcodeBaseOperator(Opcodes.UNARY_INVERT, static_eval=lambda scope, x: ~x[0].evaluate_static_value(scope)),
        "not": OpcodeBaseOperator(Opcodes.UNARY_NOT, static_eval=lambda scope, x: not x[0].evaluate_static_value(scope)),
        "!": OpcodeBaseOperator(Opcodes.UNARY_NOT, static_eval=lambda scope, x: not x[0].evaluate_static_value(scope)),
    }

    PREFIX_OPERATORS = {
        "sum": (SumOperator(), None, True, True),
        "prod": (ProdOperator(), None, True, True),
        "avg": (AvgOperator(), None, True, True),
        "avgi": (AvgIOperator(), None, True, True),
        "tuple": (TupleOperator(), None, True, True),
        "list": (ListOperator(), None, True, True),
        "set": (SetOperator(), None, True, True),
        "dict": (DictOperator(), None, True, True),
    }

    # todo: inplace variants
