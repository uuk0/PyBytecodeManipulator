import dis
import itertools
import json
import os.path
import sys
import typing


def create_instruction(
    opname_or_code: typing.Union[str, int],
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


if PY_VERSION >= (3, 11):
    def createCall(arg_count: int, func_type="function"):
        return [
            create_instruction("PRECALL_"+func_type.upper(), arg_count),
            create_instruction("CALL"),
        ]
else:
    def createCall(arg_count: int, func_type="function"):
        return [
            create_instruction("CALL_"+func_type.upper(), arg_count)
        ]


__UNIQUE_VALUE = 0


def _unique_value():
    global __UNIQUE_VALUE
    v = __UNIQUE_VALUE
    __UNIQUE_VALUE += 1
    return v


class Opcodes:
    """
    Class of all Opcodes
    Valid at any point in python's history we support with this library
    """

    POP_TOP = _unique_value()
    ROT_TWO = _unique_value()
    ROT_THREE = _unique_value()
    DUP_TOP = _unique_value()
    DUP_TOP_TWO = _unique_value()
    ROT_FOUR = _unique_value()
    NOP = _unique_value()
    UNARY_POSITIVE = _unique_value()
    UNARY_NEGATIVE = _unique_value()
    UNARY_NOT = _unique_value()
    UNARY_INVERT = _unique_value()
    BINARY_MATRIX_MULTIPLY = _unique_value()
    INPLACE_MATRIX_MULTIPLY = _unique_value()
    BINARY_POWER = _unique_value()
    BINARY_MULTIPLY = _unique_value()
    BINARY_MODULO = _unique_value()
    BINARY_ADD = _unique_value()
    BINARY_SUBTRACT = _unique_value()
    BINARY_SUBSCR = _unique_value()
    BINARY_FLOOR_DIVIDE = _unique_value()
    BINARY_TRUE_DIVIDE = _unique_value()
    INPLACE_FLOOR_DIVIDE = _unique_value()
    INPLACE_TRUE_DIVIDE = _unique_value()
    PUSH_EXC_INFO = _unique_value()
    RERAISE = _unique_value()
    WITH_EXCEPT_START = _unique_value()
    GET_AITER = _unique_value()
    GET_ANEXT = _unique_value()
    BEFORE_ASYNC_WITH = _unique_value()
    BEFORE_WITH = _unique_value()
    END_ASYNC_FOR = _unique_value()
    INPLACE_ADD = _unique_value()
    INPLACE_SUBTRACT = _unique_value()
    INPLACE_MULTIPLY = _unique_value()
    INPLACE_MODULO = _unique_value()
    STORE_SUBSCR = _unique_value()
    DELETE_SUBSCR = _unique_value()
    BINARY_LSHIFT = _unique_value()
    BINARY_RSHIFT = _unique_value()
    BINARY_AND = _unique_value()
    BINARY_XOR = _unique_value()
    BINARY_OR = _unique_value()
    INPLACE_POWER = _unique_value()
    GET_ITER = _unique_value()
    GET_YIELD_FROM_ITER = _unique_value()
    PRINT_EXPR = _unique_value()
    LOAD_BUILD_CLASS = _unique_value()
    YIELD_FROM = _unique_value()
    GET_AWAITABLE = _unique_value()
    LOAD_ASSERTION_ERROR = _unique_value()
    RETURN_GENERATOR = _unique_value()
    INPLACE_LSHIFT = _unique_value()
    INPLACE_RSHIFT = _unique_value()
    INPLACE_AND = _unique_value()
    INPLACE_XOR = _unique_value()
    INPLACE_OR = _unique_value()
    LIST_TO_TUPLE = _unique_value()
    RETURN_VALUE = _unique_value()
    IMPORT_STAR = _unique_value()
    SETUP_ANNOTATIONS = _unique_value()
    YIELD_VALUE = _unique_value()
    POP_BLOCK = _unique_value()
    ASYNC_GEN_WRAP = _unique_value()
    POP_EXCEPT = _unique_value()
    HAVE_ARGUMENT = _unique_value()
    STORE_NAME = _unique_value()
    DELETE_NAME = _unique_value()
    UNPACK_SEQUENCE = _unique_value()
    FOR_ITER = _unique_value()
    UNPACK_EX = _unique_value()
    STORE_ATTR = _unique_value()
    DELETE_ATTR = _unique_value()
    STORE_GLOBAL = _unique_value()
    DELETE_GLOBAL = _unique_value()
    LOAD_CONST = _unique_value()
    LOAD_NAME = _unique_value()
    BUILD_TUPLE = _unique_value()
    BUILD_LIST = _unique_value()
    BUILD_SET = _unique_value()
    BUILD_MAP = _unique_value()
    LOAD_ATTR = _unique_value()
    COMPARE_OP = _unique_value()
    IMPORT_NAME = _unique_value()
    IMPORT_FROM = _unique_value()
    JUMP_FORWARD = _unique_value()
    JUMP_IF_FALSE_OR_POP = _unique_value()
    JUMP_IF_TRUE_OR_POP = _unique_value()
    JUMP_ABSOLUTE = _unique_value()
    POP_JUMP_IF_FALSE = _unique_value()
    POP_JUMP_IF_TRUE = _unique_value()
    LOAD_GLOBAL = _unique_value()
    IS_OP = _unique_value()
    CONTAINS_OP = _unique_value()
    COPY = _unique_value()
    JUMP_IF_NOT_EXC_MATCH = _unique_value()
    SETUP_FINALLY = _unique_value()
    BINARY_OP = _unique_value()
    SEND = _unique_value()
    LOAD_FAST = _unique_value()
    STORE_FAST = _unique_value()
    DELETE_FAST = _unique_value()
    POP_JUMP_IF_NOT_NONE = _unique_value()
    POP_JUMP_IF_NONE = _unique_value()
    RAISE_VARARGS = _unique_value()
    CALL_FUNCTION = _unique_value()
    LOAD_FAST__LOAD_FAST = _unique_value()
    MAKE_FUNCTION = _unique_value()
    BUILD_SLICE = _unique_value()
    JUMP_NO_INTERRUPT = _unique_value()
    MAKE_CELL = _unique_value()
    LOAD_CLOSURE = _unique_value()
    LOAD_DEREF = _unique_value()
    STORE_DEREF = _unique_value()
    DELETE_DEREF = _unique_value()
    STORE_FAST__LOAD_FAST = _unique_value()
    LOAD_FAST__LOAD_CONST = _unique_value()
    CALL_FUNCTION_KW = _unique_value()
    CALL_FUNCTION_EX = _unique_value()
    SETUP_WITH = _unique_value()
    LOAD_CONST__LOAD_FAST = _unique_value()
    LIST_APPEND = _unique_value()
    SET_ADD = _unique_value()
    MAP_ADD = _unique_value()
    LOAD_CLASSDEREF = _unique_value()
    COPY_FREE_VARS = _unique_value()
    EXTENDED_ARG = _unique_value()
    STORE_FAST__STORE_FAST = _unique_value()
    RESUME = _unique_value()
    SETUP_ASYNC_WITH = _unique_value()
    FORMAT_VALUE = _unique_value()
    BUILD_CONST_KEY_MAP = _unique_value()
    BUILD_STRING = _unique_value()
    LOAD_METHOD = _unique_value()
    CALL_METHOD = _unique_value()
    LIST_EXTEND = _unique_value()
    SET_UPDATE = _unique_value()
    DICT_MERGE = _unique_value()
    DICT_UPDATE = _unique_value()
    PRECALL_METHOD = _unique_value()
    CALL_NO_KW = _unique_value()
    CALL_KW = _unique_value()
    PUSH_NULL = _unique_value()
    GET_LEN = _unique_value()
    MATCH_MAPPING = _unique_value()
    MATCH_SEQUENCE = _unique_value()
    MATCH_KEYS = _unique_value()
    CHECK_EXC_MATCH = _unique_value()
    CHECK_EG_MATCH = _unique_value()
    PREP_RERAISE_STAR = _unique_value()
    SWAP = _unique_value()
    POP_JUMP_FORWARD_IF_FALSE = _unique_value()
    POP_JUMP_FORWARD_IF_TRUE = _unique_value()
    POP_JUMP_FORWARD_IF_NOT_NONE = _unique_value()
    POP_JUMP_FORWARD_IF_NONE = _unique_value()
    JUMP_BACKWARD_NO_INTERRUPT = _unique_value()
    JUMP_BACKWARD = _unique_value()
    PRECALL = _unique_value()
    CALL = _unique_value()
    KW_NAMES = _unique_value()
    POP_JUMP_BACKWARD_IF_NOT_NONE = _unique_value()
    POP_JUMP_BACKWARD_IF_NONE = _unique_value()
    POP_JUMP_BACKWARD_IF_FALSE = _unique_value()
    POP_JUMP_BACKWARD_IF_TRUE = _unique_value()
    GET_LEN = _unique_value()

    BINARY_OP_ADAPTIVE = _unique_value()
    BINARY_OP_ADD_FLOAT = _unique_value()
    BINARY_OP_ADD_INT = _unique_value()
    BINARY_OP_ADD_UNICODE = _unique_value()
    BINARY_OP_INPLACE_ADD_UNICODE = _unique_value()
    BINARY_OP_MULTIPLY_FLOAT = _unique_value()
    BINARY_OP_MULTIPLY_INT = _unique_value()
    BINARY_OP_SUBTRACT_FLOAT = _unique_value()
    BINARY_OP_SUBTRACT_INT = _unique_value()
    BINARY_SUBSCR_ADAPTIVE = _unique_value()
    BINARY_SUBSCR_DICT = _unique_value()
    BINARY_SUBSCR_GETITEM = _unique_value()
    BINARY_SUBSCR_LIST_INT = _unique_value()
    BINARY_SUBSCR_TUPLE_INT = _unique_value()
    CALL_ADAPTIVE = _unique_value()
    CALL_PY_EXACT_ARGS = _unique_value()
    CALL_PY_WITH_DEFAULTS = _unique_value()
    COMPARE_OP_ADAPTIVE = _unique_value()
    COMPARE_OP_FLOAT_JUMP = _unique_value()
    COMPARE_OP_INT_JUMP = _unique_value()
    COMPARE_OP_STR_JUMP = _unique_value()
    EXTENDED_ARG_QUICK = _unique_value()
    JUMP_BACKWARD_QUICK = _unique_value()
    LOAD_ATTR_ADAPTIVE = _unique_value()
    LOAD_ATTR_INSTANCE_VALUE = _unique_value()
    LOAD_ATTR_MODULE = _unique_value()
    LOAD_ATTR_SLOT = _unique_value()
    LOAD_ATTR_WITH_HINT = _unique_value()
    LOAD_GLOBAL_ADAPTIVE = _unique_value()
    LOAD_GLOBAL_BUILTIN = _unique_value()
    LOAD_GLOBAL_MODULE = _unique_value()
    LOAD_METHOD_ADAPTIVE = _unique_value()
    LOAD_METHOD_CLASS = _unique_value()
    LOAD_METHOD_MODULE = _unique_value()
    LOAD_METHOD_NO_DICT = _unique_value()
    LOAD_METHOD_WITH_DICT = _unique_value()
    LOAD_METHOD_WITH_VALUES = _unique_value()
    PRECALL_ADAPTIVE = _unique_value()
    PRECALL_BOUND_METHOD = _unique_value()
    PRECALL_BUILTIN_CLASS = _unique_value()
    PRECALL_BUILTIN_FAST_WITH_KEYWORDS = _unique_value()
    PRECALL_METHOD_DESCRIPTOR_FAST_WITH_KEYWORDS = _unique_value()
    PRECALL_NO_KW_BUILTIN_FAST = _unique_value()
    PRECALL_NO_KW_BUILTIN_O = _unique_value()
    PRECALL_NO_KW_ISINSTANCE = _unique_value()
    PRECALL_NO_KW_LEN = _unique_value()
    PRECALL_NO_KW_LIST_APPEND = _unique_value()
    PRECALL_NO_KW_METHOD_DESCRIPTOR_FAST = _unique_value()
    PRECALL_NO_KW_METHOD_DESCRIPTOR_NOARGS = _unique_value()
    PRECALL_NO_KW_METHOD_DESCRIPTOR_O = _unique_value()
    PRECALL_NO_KW_STR_1 = _unique_value()
    PRECALL_NO_KW_TUPLE_1 = _unique_value()
    PRECALL_NO_KW_TYPE_1 = _unique_value()
    PRECALL_PYFUNC = _unique_value()
    RESUME_QUICK = _unique_value()
    STORE_ATTR_ADAPTIVE = _unique_value()
    STORE_ATTR_INSTANCE_VALUE = _unique_value()
    STORE_ATTR_SLOT = _unique_value()
    STORE_ATTR_WITH_HINT = _unique_value()
    STORE_SUBSCR_ADAPTIVE = _unique_value()
    STORE_SUBSCR_DICT = _unique_value()
    STORE_SUBSCR_LIST_INT = _unique_value()
    UNPACK_SEQUENCE_ADAPTIVE = _unique_value()
    UNPACK_SEQUENCE_LIST = _unique_value()
    UNPACK_SEQUENCE_TUPLE = _unique_value()
    UNPACK_SEQUENCE_TWO_TUPLE = _unique_value()
    DO_TRACING = _unique_value()


with open(f"{os.path.dirname(__file__)}/data/py{sys.version_info.major}.{sys.version_info.minor}_opcodes.json") as f:
    OPCODE_DATA = json.load(f)


__MISSING = []


for key, value in itertools.chain(OPCODE_DATA["opcodes"].items(), OPCODE_DATA.setdefault("specialize", {}).items()):
    if hasattr(Opcodes, key):
        setattr(Opcodes, key, value)
    else:
        __MISSING.append(key)
        print(f"Skipping Opcode {key} with ID {value}")


print("\n".join(f"    {name} = _unique_value()" for name in __MISSING))


for attr in list(Opcodes.__dict__.keys()):
    if attr.startswith("__"): continue

    if attr not in OPCODE_DATA["opcodes"] and attr not in OPCODE_DATA["specialize"]:
        delattr(Opcodes, attr)
