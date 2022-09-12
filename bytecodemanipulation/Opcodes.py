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

    INTERMEDIATE_INNER_RETURN = 256
    INTERMEDIATE_OUTER_RETURN = 257
    INTERMEDIATE_LOAD_FAST = 258


OPCODE2NAME = {}
OPNAME2CODE = {}

for key, value in Opcodes.__dict__.items():
    key: str
    if key.isupper() and isinstance(value, int):
        OPNAME2CODE[key] = value
        OPCODE2NAME[value] = key


END_CONTROL_FLOW = (
    Opcodes.RETURN_VALUE,
    Opcodes.RERAISE,
    Opcodes.RAISE_VARARGS,
    Opcodes.INTERMEDIATE_OUTER_RETURN,
    Opcodes.INTERMEDIATE_INNER_RETURN,
)

HAS_NAME = (
    Opcodes.STORE_NAME,
    Opcodes.DELETE_NAME,
    Opcodes.LOAD_NAME,
    Opcodes.STORE_ATTR,
    Opcodes.DELETE_ATTR,
    Opcodes.LOAD_ATTR,
    Opcodes.STORE_GLOBAL,
    Opcodes.DELETE_GLOBAL,
    Opcodes.LOAD_GLOBAL,
    Opcodes.IMPORT_NAME,
    Opcodes.IMPORT_FROM,
    Opcodes.LOAD_METHOD,
)

HAS_GLOBAL = (
    Opcodes.STORE_GLOBAL,
    Opcodes.DELETE_GLOBAL,
    Opcodes.LOAD_GLOBAL,
)

HAS_CONST = (Opcodes.LOAD_CONST,)

HAS_LOCAL = (
    Opcodes.LOAD_FAST,
    Opcodes.STORE_FAST,
    Opcodes.DELETE_FAST,
    Opcodes.INTERMEDIATE_LOAD_FAST,
)

HAS_JUMP_ABSOLUTE = (
    Opcodes.JUMP_ABSOLUTE,
    Opcodes.JUMP_IF_FALSE_OR_POP,
    Opcodes.JUMP_IF_TRUE_OR_POP,
    Opcodes.JUMP_IF_NOT_EXC_MATCH,
    Opcodes.POP_JUMP_IF_FALSE,
    Opcodes.POP_JUMP_IF_TRUE,
    Opcodes.INTERMEDIATE_INNER_RETURN,
)

HAS_JUMP_FORWARD = (
    Opcodes.FOR_ITER,
    Opcodes.JUMP_FORWARD,
    Opcodes.SETUP_FINALLY,
    Opcodes.SETUP_WITH,
    Opcodes.SETUP_ASYNC_WITH,
)

UNCONDITIONAL_JUMPS = (
    Opcodes.JUMP_ABSOLUTE,
    Opcodes.JUMP_FORWARD,
    Opcodes.INTERMEDIATE_INNER_RETURN,
)