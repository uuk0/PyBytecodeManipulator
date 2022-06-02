import dis
import sys
import unittest

from bytecodemanipulation.util import Opcodes

from bytecodemanipulation.CodeOptimiser import optimise_code, optimise_store_load_pairs, remove_store_fast_without_usage, remove_load_dup_pop, remove_create_primitive_pop, trace_load_const_store_fast_load_fast
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper


class TestOptimizerSystem(unittest.TestCase):
    # These examples operate all on the same function type, as there is a lot of stuff to do for removing the
    # variable "a"

    def test_store_load_pair(self):
        def target():
            a = 10
            return a + 1

        self.assertEqual(target(), 11)

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_FAST)

        optimise_store_load_pairs(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertEqual(instance.instruction_listing[1].opcode, Opcodes.DUP_TOP)
        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.STORE_FAST)

        self.assertEqual(target(), 11)

    def test_remove_store_fast_without_use(self):
        def target():
            a = 10
            return a + 1

        self.assertEqual(target(), 11)

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_FAST)

        optimise_store_load_pairs(instance)
        remove_store_fast_without_usage(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertNotEqual(instance.instruction_listing[2].opcode, Opcodes.STORE_FAST)

        self.assertEqual(instance.instruction_listing[1].opcode, Opcodes.DUP_TOP)

        self.assertEqual(target(), 11)

    def test_remove_dup_pop(self):
        def target():
            a = 10
            return a + 1

        self.assertEqual(target(), 11)

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_FAST)

        optimise_store_load_pairs(instance)
        remove_store_fast_without_usage(instance)
        remove_load_dup_pop(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertNotEqual(instance.instruction_listing[1].opcode, Opcodes.DUP_TOP)

        self.assertEqual(target(), 11)

    def test_above_combined(self):
        def target():
            a = 10
            return a + 1

        self.assertEqual(target(), 11)

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_FAST)

        optimise_code(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertNotEqual(instance.instruction_listing[1].opcode, Opcodes.DUP_TOP)

        self.assertEqual(target(), 11)

    # Again, that one function has multiple optimisations
    def test_primitive_build_remove_simple(self):
        def target():
            a = 10
            (a, 34345)

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[4].opcode, Opcodes.BUILD_TUPLE)

        remove_create_primitive_pop(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertNotEqual(instance.instruction_listing[4].opcode, Opcodes.BUILD_TUPLE)

    def test_remove_unused_local_2(self):
        def target():
            a = 10
            (a, 34345)

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[1].opcode, Opcodes.STORE_FAST)

        remove_create_primitive_pop(instance)
        remove_load_dup_pop(instance)  # remove the leftover LOAD_XX POP_TOP pairs
        remove_store_fast_without_usage(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertNotEqual(instance.instruction_listing[1].opcode, Opcodes.STORE_FAST)

    def test_primitive_build_remove_map(self):
        def target():
            a = 10
            {a: 34345}

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[4].opcode, Opcodes.BUILD_MAP)

        remove_create_primitive_pop(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertNotEqual(instance.instruction_listing[4].opcode, Opcodes.BUILD_MAP)

    def test_const_store_load(self):
        def target():
            a = 10
            return a

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_FAST)

        trace_load_const_store_fast_load_fast(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_CONST)

    def test_const_store_load_2(self):
        def target():
            a = 10
            return a

        instance = BytecodePatchHelper(target)

        self.assertEqual(instance.instruction_listing[2].opcode, Opcodes.LOAD_FAST)

        optimise_code(instance)

        instance.store()
        instance.patcher.applyPatches()

        self.assertEqual(instance.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(instance.instruction_listing[0].argval, 10)

