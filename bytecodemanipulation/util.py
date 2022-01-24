import dis
import sys
import typing


def create_instruction(
    opname_or_code: str | int,
    arg_pt: int = 0,
    arg_val: typing.Any = None,
    offset=-1,
    start_line=None,
    is_jump_target=False,
):
    if isinstance(opname_or_code, str):
        opname = opname_or_code
        opcode = dis.opmap[opname]
    else:
        opcode = opname_or_code
        opname = dis.opname[opcode]

    return dis.Instruction(
        opname, opcode, arg_pt, arg_val, arg_val, offset, start_line, is_jump_target
    )


PY_VERSION = sys.version_info.major, sys.version_info.minor


class Opcodes:
    POP_TOP = 1
    ROT_TWO = 2
    ROT_THREE = 3
    DUP_TOP = 4
    DUP_TOP_TWO = 5
    ROT_FOUR = 6

    NOP = 9
    UNARY_POSITIVE = 10
    UNARY_NEGATIVE = 11
    UNARY_NOT = 12

    UNARY_INVERT = 15

    BINARY_MATRIX_MULTIPLY = 16
    INPLACE_MATRIX_MULTIPLY = 17

    BINARY_POWER = 19
    BINARY_MULTIPLY = 20

    BINARY_MODULO = 22
    BINARY_ADD = 23
    BINARY_SUBTRACT = 24
    BINARY_SUBSCR = 25
    BINARY_FLOOR_DIVIDE = 26
    BINARY_TRUE_DIVIDE = 27
    INPLACE_FLOOR_DIVIDE = 28
    INPLACE_TRUE_DIVIDE = 29

    if PY_VERSION >= (3, 11):
        PUSH_EXC_INFO = 35

    RERAISE = 48
    WITH_EXCEPT_START = 49
    GET_AITER = 50
    GET_ANEXT = 51
    BEFORE_ASYNC_WITH = 52

    if PY_VERSION >= (3, 11):
        BEFORE_WITH = 53

    END_ASYNC_FOR = 54
    INPLACE_ADD = 55
    INPLACE_SUBTRACT = 56
    INPLACE_MULTIPLY = 57

    INPLACE_MODULO = 59
    STORE_SUBSCR = 60
    DELETE_SUBSCR = 61
    BINARY_LSHIFT = 62
    BINARY_RSHIFT = 63
    BINARY_AND = 64
    BINARY_XOR = 65
    BINARY_OR = 66
    INPLACE_POWER = 67
    GET_ITER = 68
    GET_YIELD_FROM_ITER = 69

    PRINT_EXPR = 70
    LOAD_BUILD_CLASS = 71

    if PY_VERSION < (3, 11):
        YIELD_FROM = 72

    GET_AWAITABLE = 73
    LOAD_ASSERTION_ERROR = 74

    if PY_VERSION >= (3, 11):
        RETURN_GENERATOR = 75

    INPLACE_LSHIFT = 75
    INPLACE_RSHIFT = 76
    INPLACE_AND = 77
    INPLACE_XOR = 78
    INPLACE_OR = 79

    LIST_TO_TUPLE = 82
    RETURN_VALUE = 83
    IMPORT_STAR = 84
    SETUP_ANNOTATIONS = 85
    YIELD_VALUE = 86

    if PY_VERSION < (3, 11):
        POP_BLOCK = 87

    POP_EXCEPT = 89

    HAVE_ARGUMENT = 90  # Opcodes from here have an argument:

    STORE_NAME = 90  # Index in name list
    DELETE_NAME = 91  # ""
    UNPACK_SEQUENCE = 92  # Number of tuple items
    FOR_ITER = 93
    UNPACK_EX = 94
    STORE_ATTR = 95  # Index in name list
    DELETE_ATTR = 96  # ""
    STORE_GLOBAL = 97  # ""
    DELETE_GLOBAL = 98  # ""
    LOAD_CONST = 100  # Index in const list
    LOAD_NAME = 101  # Index in name list
    BUILD_TUPLE = 102  # Number of tuple items
    BUILD_LIST = 103  # Number of list items
    BUILD_SET = 104  # Number of set items
    BUILD_MAP = 105  # Number of dict entries
    LOAD_ATTR = 106  # Index in name list
    COMPARE_OP = 107  # Comparison operator
    IMPORT_NAME = 108  # Index in name list
    IMPORT_FROM = 109  # Index in name list

    JUMP_FORWARD = 110  # Number of bytes to skip
    JUMP_IF_FALSE_OR_POP = 111  # Target byte offset from beginning of code
    JUMP_IF_TRUE_OR_POP = 112  # ""
    JUMP_ABSOLUTE = 113  # ""
    POP_JUMP_IF_FALSE = 114  # ""
    POP_JUMP_IF_TRUE = 115  # ""

    LOAD_GLOBAL = 116  # Index in name list

    IS_OP = 117
    CONTAINS_OP = 118

    if PY_VERSION >= (3, 11):
        COPY = 120

    JUMP_IF_NOT_EXC_MATCH = 121

    if PY_VERSION < (3, 11):
        SETUP_FINALLY = 122  # Distance to target address
    else:
        BINARY_OP = 122

    if PY_VERSION > (3, 11):
        SEND = 123

    LOAD_FAST = 124  # Local variable number
    STORE_FAST = 125  # Local variable number
    DELETE_FAST = 126  # Local variable number

    if PY_VERSION > (3, 11):
        POP_JUMP_IF_NOT_NONE = 128
        POP_JUMP_IF_NONE = 129

    RAISE_VARARGS = 130  # Number of raise arguments (1, 2, or 3)

    if PY_VERSION < (3, 11):
        CALL_FUNCTION = 131  # #args
    else:
        LOAD_FAST__LOAD_FAST = 131

    MAKE_FUNCTION = 132  # Flags
    BUILD_SLICE = 133  # Number of items

    if PY_VERSION >= (3, 11):
        JUMP_NO_INTERRUPT = 134

    LOAD_CLOSURE = 135

    if PY_VERSION >= (3, 11):
        MAKE_CELL = 135
        LOAD_CLOSURE = 136
        LOAD_DEREF = 137
        STORE_DEREF = 138
        DELETE_DEREF = 139

    else:
        LOAD_CLOSURE = 135
        LOAD_DEREF = 136
        STORE_DEREF = 137
        DELETE_DEREF = 138

    if PY_VERSION >= (3, 11):
        STORE_FAST__LOAD_FAST = 140
        LOAD_FAST__LOAD_CONST = 141

    if PY_VERSION < (3, 11):
        CALL_FUNCTION_KW = 141  # #args + #kwargs

    CALL_FUNCTION_EX = 142  # Flags

    if PY_VERSION < (3, 11):
        SETUP_WITH = 143

    if PY_VERSION >= (3, 11):
        LOAD_CONST__LOAD_FAST = 143

    LIST_APPEND = 145
    SET_ADD = 146
    MAP_ADD = 147

    LOAD_CLASSDEREF = 148

    if PY_VERSION >= (3, 11):
        COPY_FREE_VARS = 149

    EXTENDED_ARG = 144

    if PY_VERSION >= (3, 11):
        STORE_FAST__STORE_FAST = 150
        RESUME = 151

    SETUP_ASYNC_WITH = 154

    FORMAT_VALUE = 155
    BUILD_CONST_KEY_MAP = 156
    BUILD_STRING = 157

    LOAD_METHOD = 160

    if PY_VERSION < (3, 11):
        CALL_METHOD = 161

    LIST_EXTEND = 162
    SET_UPDATE = 163
    DICT_MERGE = 164
    DICT_UPDATE = 165

    if PY_VERSION >= (3, 11):
        PRECALL_METHOD = 168
        CALL_NO_KW = 169
        CALL_KW = 170
