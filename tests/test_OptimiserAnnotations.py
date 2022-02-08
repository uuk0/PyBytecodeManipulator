import dis
import timeit
from unittest import TestCase

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
        min = max

        self.assertEqual(min(1, 2), 2)
        self.assertEqual(target(1, 2), 1)

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
