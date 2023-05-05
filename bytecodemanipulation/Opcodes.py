import sys
import typing


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
    GET_LEN = 30
    MATCH_MAPPING = 31
    MATCH_SEQUENCE = 32
    MATCH_KEYS = 33
    COPY_DICT_WITHOUT_KEYS = 34

    WITH_EXCEPT_START = 49
    GET_AITER = 50
    GET_ANEXT = 51
    BEFORE_ASYNC_WITH = 52

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
    YIELD_FROM = 72
    GET_AWAITABLE = 73
    LOAD_ASSERTION_ERROR = 74
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
    ROT_N = 99
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
    RERAISE = 119

    JUMP_IF_NOT_EXC_MATCH = 121
    SETUP_FINALLY = 122  # Distance to target address

    LOAD_FAST = 124  # Local variable number
    STORE_FAST = 125  # Local variable number
    DELETE_FAST = 126  # Local variable number

    GEN_START = 129  # Kind of generator/coroutine
    RAISE_VARARGS = 130  # Number of raise arguments (1, 2, or 3
    CALL_FUNCTION = 131  # #args
    MAKE_FUNCTION = 132  # Flags
    BUILD_SLICE = 133  # Number of items

    LOAD_CLOSURE = 135
    LOAD_DEREF = 136
    STORE_DEREF = 137
    DELETE_DEREF = 138

    CALL_FUNCTION_KW = 141  # #args + #kwargs
    CALL_FUNCTION_EX = 142  # Flags
    SETUP_WITH = 143
    EXTENDED_ARG = 144
    LIST_APPEND = 145
    SET_ADD = 146
    MAP_ADD = 147
    LOAD_CLASSDEREF = 148

    MATCH_CLASS = 152

    SETUP_ASYNC_WITH = 154
    FORMAT_VALUE = 155
    BUILD_CONST_KEY_MAP = 156
    BUILD_STRING = 157

    LOAD_METHOD = 160
    CALL_METHOD = 161
    LIST_EXTEND = 162
    SET_UPDATE = 163
    DICT_MERGE = 164
    DICT_UPDATE = 165

    # Since python 3.11
    if sys.version_info.minor >= 11 or typing.TYPE_CHECKING:
        CACHE = 166
        PUSH_NULL = 167
        PUSH_EXC_INFO = 168
        CHECK_EXC_MATCH = 169
        CHECK_EG_MATCH = 170
        BEFORE_WITH = 171
        RETURN_GENERATOR = 172
        ASYNC_GEN_WRAP = 173
        PREP_RERAISE_STAR = 174
        SWAP = 175
        POP_JUMP_FORWARD_IF_FALSE = 176
        POP_JUMP_FORWARD_IF_TRUE = 177
        COPY = 178
        BINARY_OP = 179
        SEND = 180
        POP_JUMP_FORWARD_IF_NOT_NONE = 181
        POP_JUMP_FORWARD_IF_NONE = 182
        JUMP_BACKWARD_NO_INTERRUPT = 183
        MAKE_CELL = 184
        JUMP_BACKWARD = 185
        COPY_FREE_VARS = 186
        RESUME = 187
        PRECALL = 188
        CALL = 189
        KW_NAMES = 190
        POP_JUMP_BACKWARD_IF_NOT_NONE = 191
        POP_JUMP_BACKWARD_IF_NONE = 192
        POP_JUMP_BACKWARD_IF_FALSE = 193
        POP_JUMP_BACKWARD_IF_TRUE = 194

    INTERMEDIATE_INNER_RETURN = 256
    INTERMEDIATE_OUTER_RETURN = 257
    INTERMEDIATE_LOAD_FAST = 258
    BYTECODE_LABEL = 259
    MACRO_PARAMETER_EXPANSION = 260
    STATIC_ATTRIBUTE_ACCESS = 261
    MACRO_RETURN_VALUE = 262
    MACRO_LOAD_PARAMETER = 263
    MACRO_STORE_PARAMETER = 264


OPCODE2NAME = {}
OPNAME2CODE = {}


def init_maps():
    OPNAME2CODE.clear()
    OPCODE2NAME.clear()

    for key, value in Opcodes.__dict__.items():
        key: str
        if key.isupper() and isinstance(value, int):
            OPNAME2CODE[key] = value
            OPCODE2NAME[value] = key


END_CONTROL_FLOW: typing.List[int] = []
HAS_NAME: typing.List[int] = []
HAS_GLOBAL: typing.List[int] = []
HAS_CONST: typing.List[int] = []
HAS_LOCAL: typing.List[int] = []
HAS_JUMP_ABSOLUTE: typing.List[int] = []
HAS_JUMP_FORWARD: typing.List[int] = []
HAS_JUMP_BACKWARDS: typing.List[int] = []
UNCONDITIONAL_JUMPS: typing.List[int] = []
HAS_CELL_VARIABLE: typing.List[int] = []

SIDE_EFFECT_FREE_LOADS: typing.List[int] = []
