from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.OpAssembly import AbstractOpAssembly
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.Opcodes import Opcodes


@Parser.register
class OpAssembly(AbstractOpAssembly):
    BINARY_OPS = {
        "+": Opcodes.BINARY_ADD,
        "-": Opcodes.BINARY_SUBTRACT,
        "*": Opcodes.BINARY_MULTIPLY,
        "/": Opcodes.BINARY_TRUE_DIVIDE,
        "//": Opcodes.BINARY_FLOOR_DIVIDE,
        "**": Opcodes.BINARY_MULTIPLY,
        "%": Opcodes.BINARY_MODULO,
        "&": Opcodes.BINARY_AND,
        "|": Opcodes.BINARY_OR,
        "^": Opcodes.BINARY_XOR,
        ">>": Opcodes.BINARY_RSHIFT,
        "<<": Opcodes.BINARY_LSHIFT,
        "@": Opcodes.BINARY_MATRIX_MULTIPLY,
        "is": (Opcodes.IS_OP, 0),
        "!is": (Opcodes.IS_OP, 1),
        "in": (Opcodes.CONTAINS_OP, 0),
        "!in": (Opcodes.CONTAINS_OP, 1),
        "<": (Opcodes.COMPARE_OP, 0),
        "<=": (Opcodes.COMPARE_OP, 1),
        "==": (Opcodes.COMPARE_OP, 2),
        "!=": (Opcodes.COMPARE_OP, 3),
        ">": (Opcodes.COMPARE_OP, 4),
        ">=": (Opcodes.COMPARE_OP, 5),
        # todo: is there a better way?
        "xor": (Opcodes.COMPARE_OP, 3),
        "!xor": (Opcodes.COMPARE_OP, 2),
        ":=": lambda lhs, rhs, function, scope: rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.DUP_TOP)]
        + lhs.emit_store_bytecodes(function, scope),
        "isinstance": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, isinstance)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
        "issubclass": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, issubclass)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
        "hasattr": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, hasattr)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
        "getattr": lambda lhs, rhs, function, scope: [
            Instruction(function, -1, Opcodes.LOAD_CONST, getattr)
        ]
        + lhs.emit_bytecodes(function, scope)
        + rhs.emit_bytecodes(function, scope)
        + [Instruction(function, -1, Opcodes.CALL_FUNCTION, arg=2)],
    }

    SINGLE_OPS = {
        "-": Opcodes.UNARY_NEGATIVE,
        "+": Opcodes.UNARY_POSITIVE,
        "~": Opcodes.UNARY_INVERT,
        "not": Opcodes.UNARY_NOT,
        "!": Opcodes.UNARY_NOT,
    }

    # todo: and, or, nand, nor, inplace variants
