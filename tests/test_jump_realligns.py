from dis import Instruction

import tests.test_space
from bytecodemanipulation import MutableCodeObject
from bytecodemanipulation.Transformers import TransformationHandler
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.util import create_instruction
from unittest import TestCase


class TestJumpAlignment(TestCase):
    def setUp(self):
        TransformationHandler.LOCKED = False

    def test_simple_remove(self):
        test = False

        def a():
            nonlocal test
            test = True

        patcher = MutableCodeObject.MutableCodeObject(a)
        helper = BytecodePatchHelper(patcher)

        a()
        self.assertTrue(test)
        test = False

        helper.deleteRegion(0, 2)
        helper.store()
        patcher.applyPatches()
        a()
        self.assertFalse(test)

    def test_simple_insert(self):
        test = False

        def a():
            pass

        patcher = MutableCodeObject.MutableCodeObject(a)
        helper = BytecodePatchHelper(patcher)

        a()
        self.assertFalse(test)

        helper.insertRegion(
            0,
            [
                create_instruction("LOAD_CONST", arg_pt=patcher.ensureConstant(True)),
                create_instruction("RETURN_VALUE"),
            ],
        )
        helper.store()
        patcher.applyPatches()
        # helper.print_stats()
        self.assertEqual(a(), True)

    def test_jump_change(self):
        test1 = False
        test2 = False

        def a(arg):
            if arg:
                nonlocal test1
                test1 = True
            else:
                nonlocal test2
                test2 = True

        a(False)
        self.assertFalse(test1)
        self.assertTrue(test2)
        test2 = False

        a(True)
        self.assertTrue(test1)
        self.assertFalse(test2)
        test1 = False

        patcher = MutableCodeObject.MutableCodeObject(a)
        helper = BytecodePatchHelper(patcher)

        # Delete the two instructions storing the True value in test1
        helper.deleteRegion(2, 4)
        helper.store()
        patcher.applyPatches()

        a(False)
        self.assertFalse(test1)
        self.assertTrue(test2)
        test2 = False

        a(True)
        self.assertFalse(test1)
        self.assertFalse(test2)
