import dis
import sys
import typing
import unittest

from bytecodemanipulation.CodeOptimiser import optimise_code
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

from bytecodemanipulation.InstructionMatchers import CounterMatcher
from bytecodemanipulation.Transformers import TransformationHandler
from unittest import TestCase


class TestPostInjectionOptimiser(TestCase):
    @unittest.skipUnless(sys.version_info.major <= 3 and sys.version_info.minor < 11, "until python 3.11")
    def test_optimiser_1(self):
        def test():
            a = 0
            del a

        helper = BytecodePatchHelper(test)
        optimise_code(helper)

        self.assertEqual(helper.instruction_listing[0].opname, "LOAD_CONST")
        self.assertEqual(helper.instruction_listing[0].argval, None)
        self.assertEqual(helper.instruction_listing[1].opname, "RETURN_VALUE")

        # Integrity check of the bytecode
        self.assertEqual(test(), None)

    @unittest.skipUnless(sys.version_info.major <= 3 and sys.version_info.minor < 11, "until python 3.11")
    def test_basic(self):
        invoked = 0

        def target(flag):
            # only here to make cell var integrity happy
            # should be stripped away during optimiser stage
            invoked

            # should also be stripped away, this is global access
            global TestPostInjectionOptimiser
            TestPostInjectionOptimiser

            # Should also be stripped away, is side effect free assignment
            TestPostInjectionOptimiser = TestPostInjectionOptimiser

            flag = flag

            if flag:
                return 0
            return 1

        handler = TransformationHandler()
        handler.makeFunctionArrival("test", target)

        @handler.inject_at_tail("test", inline=True)
        def inject():
            nonlocal invoked
            invoked = 4

        self.assertEqual(target(False), 1)
        self.assertEqual(invoked, 0)
        self.assertEqual(target(True), 0)
        self.assertEqual(invoked, 0)

        # Will apply the later processor first, as it is optional, and as such can break when overriding it
        handler.applyTransforms()

        self.assertEqual(target(True), 0)
        self.assertEqual(invoked, 0)
        self.assertEqual(target(False), 1)
        self.assertEqual(invoked, 4)

        # Check if it is optimised away
        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opname, "LOAD_FAST")
        self.assertEqual(
            helper.instruction_listing[0].arg,
            helper.patcher.ensureVarName("flag"),
            helper.instruction_listing[0],
        )

    def test_attribute2constant_cleanup(self):
        def target(c):
            return c.test_attribute2constant_cleanup

        handler = TransformationHandler()
        handler.makeFunctionArrival("test", target)
        handler.replace_attribute_with_constant(
            "test", "%.test_attribute2constant_cleanup", 2
        )
        handler.applyTransforms()

        helper = BytecodePatchHelper(target)

        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            self.assertEqual(helper.instruction_listing[0].opname, "LOAD_CONST")
            self.assertEqual(helper.instruction_listing[0].argval, 2)
        else:
            self.assertEqual(helper.instruction_listing[1].opname, "LOAD_CONST")
            self.assertEqual(helper.instruction_listing[1].argval, 2)
