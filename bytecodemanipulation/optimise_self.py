import dis

from bytecodemanipulation import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Optimiser import (
    guarantee_builtin_names_are_protected,
    guarantee_module_import,
    apply_now,
)


guarantee_builtin_names_are_protected()(MutableFunction.MutableFunction)
guarantee_module_import("Opcodes", Opcodes)(MutableFunction.MutableFunction)
apply_now()(MutableFunction.MutableFunction)
