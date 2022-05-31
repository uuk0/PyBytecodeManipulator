import dis
import timeit
from unittest import TestCase

from bytecodemanipulation.util import Opcodes

from bytecodemanipulation.OptimiserAnnotations import try_optimise

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

from bytecodemanipulation.OptimiserAnnotations import run_optimisations, builtins_are_static, forced_attribute_type


class TestOptimiserAnnotations(TestCase):
    def test_builtins_are_static_1(self):
        @builtins_are_static()
        def target(a, b):
            return min(a, b)

        self.assertEqual(target(1, 2), 1)

        run_optimisations()
        global min
        old_min = min
        min = max

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)

        self.assertEqual(min(1, 2), 2)
        self.assertEqual(target(1, 2), 1)

        min = old_min

    def test_builtins_are_static_min(self):
        @builtins_are_static()
        def target():
            return min(1, 2)

        self.assertEqual(target(), 1)

        run_optimisations()
        global min
        old_min = min
        min = max

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 1)

        self.assertEqual(min(1, 2), 2)
        self.assertEqual(target(), 1)

        min = old_min

    def test_builtins_are_static_max(self):
        @builtins_are_static()
        def target():
            return max(1, 2)

        self.assertEqual(target(), 2)

        run_optimisations()

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 2)

        self.assertEqual(max(1, 2), 2)
        self.assertEqual(target(), 2)

    def test_builtins_are_static_tuple(self):
        @builtins_are_static()
        def target():
            return tuple((2, 3))

        self.assertEqual(target(), (2, 3))

        run_optimisations()

        dis.dis(target)

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, (2, 3))

        self.assertEqual(target(), (2, 3))

    def test_builtins_are_static_abs(self):
        @builtins_are_static()
        def target():
            return abs(-10)

        self.assertEqual(target(), 10)

        run_optimisations()

        dis.dis(target)

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 10)

        self.assertEqual(target(), 10)

    def test_builtins_are_static_all(self):
        @builtins_are_static()
        def target():
            return all((True, True, False))

        self.assertEqual(target(), False)

        run_optimisations()

        dis.dis(target)

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, False)

        self.assertEqual(target(), False)

    def test_builtins_are_static_any(self):
        @builtins_are_static()
        def target():
            return any((True, True, False))

        self.assertEqual(target(), True)

        run_optimisations()

        dis.dis(target)

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, True)

        self.assertEqual(target(), True)

    def test_class_attribute_type_helper(self):
        """
        This does a general speed up, cycling from a few 0.01s up to 0.5 in our tests
        WARNING: test results fluctuate depending on CPU load and speculation of the CPU system
        """

        @forced_attribute_type("test", lambda: str)
        class TestCls:
            def __init__(self):
                self.test = "hello world"

            def test_func(self):
                return self.test.upper()

        self.assertEqual(TestCls().test_func(), "HELLO WORLD")

        # obj = TestCls()
        # print("before:", timeit.timeit(obj.test_func, globals=locals()))

        run_optimisations()

        helper = BytecodePatchHelper(TestCls.test_func)
        # helper.print_stats()
        # helper.enable_verbose_exceptions()
        # helper.store()

        # If we optimised it away, this becomes a LOAD_CONST instruction
        self.assertEqual(helper.instruction_listing[0].opname, "LOAD_CONST")
        self.assertEqual(TestCls().test_func(), "HELLO WORLD")

        # obj = TestCls()
        # print("after:", timeit.timeit(obj.test_func, globals=locals()))
        #
        # class TestCls:
        #     def __init__(self):
        #         self.test = "hello world"
        #
        #     def test_func(self):
        #         return self.test.upper()
        #
        # obj = TestCls()
        # print("compare:", timeit.timeit(obj.test_func, globals=locals()))

    def test_class_attribute_type_helper_subclass(self):
        """
        Checks the parent class lookup for type annotations
        """

        @forced_attribute_type("test", lambda: str)
        class TestBase:
            def __init__(self):
                self.test = "hello world"

        @try_optimise()
        class TestCls(TestBase):
            def test_func(self):
                return self.test.upper()

        self.assertEqual(TestCls().test_func(), "HELLO WORLD")

        run_optimisations()

        helper = BytecodePatchHelper(TestCls.test_func)
        helper.print_stats()
        helper.enable_verbose_exceptions()
        helper.store()

        # If we optimised it away, this becomes a LOAD_CONST instruction
        self.assertEqual(helper.instruction_listing[0].opname, "LOAD_CONST")
        self.assertEqual(TestCls().test_func(), "HELLO WORLD")

    # def test_math_standard_library_inline(self):
    #     import bytecodemanipulation.StandardLibraryAnnotations
    #     import math
    #
    #     @builtins_are_static()
    #     def target():
    #         return math.sin(0)
    #
    #     self.assertEqual(target(), True)
    #
    #     run_optimisations()
    #
    #     dis.dis(target)
    #
    #     helper = BytecodePatchHelper(target)
    #     self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
    #     self.assertEqual(helper.instruction_listing[0].argval, True)
    #
    #     self.assertEqual(target(), True)
