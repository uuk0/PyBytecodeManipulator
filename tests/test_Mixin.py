import dis
import unittest
from unittest import TestCase


from bytecodemanipulation.Mixin import *
from tests.util import compare_optimized_results

FLAG = False


class TestMixinBasic(unittest.TestCase):
    def setUp(self) -> None:
        Mixin._reset()

    def test_constructor_raises_exception(self):
        self.assertRaises(ValueError, lambda: Mixin(0))

    def test_annotation_with_non_class(self):
        mixin = Mixin(lambda: TestMixinBasic)
        self.assertRaises(TypeError, lambda: mixin(0))

    def test_annotation_with_not_implementing_class(self):
        class Example:
            pass

        mixin = Mixin(lambda: TestMixinBasic)
        self.assertRaises(ValueError, lambda: mixin(Example))

    def test_double_annotation(self):
        class Example(Mixin.Interface):
            pass

        mixin = Mixin(lambda: TestMixinBasic)
        mixin(Example)
        self.assertRaises(ValueError, lambda: mixin(Example))

    def test_functional(self):
        class Target:
            pass

        @Mixin(Target)
        class TargetMixin(Mixin.Interface):
            pass


class TestMixinApply(TestCase):
    def test_func_replacement(self):
        class XY:
            def target(self):
                return 0

        self.assertEqual(XY.target(None), 0)

        @Mixin(XY)
        class XYMixin(Mixin.Interface):
            @override("target")
            def target(self):
                return 1

        XYMixin._apply()

        self.assertEqual(XY.target(None), 1)

    def test_function_inject_at_head(self):
        class XY:
            def target(self):
                return 2

        @Mixin(XY)
        class XYMixin(Mixin.Interface):
            @inject_at("target", InjectionPosition.HEAD)
            def target(self):
                global FLAG
                FLAG = True

        XYMixin._apply()

        def compare():
            global FLAG
            FLAG = True
            return 2

        compare_optimized_results(
            self,
            XY.target,
            compare,
        )

    def test_function_inject_at_return(self):
        class XY:
            def target(self):
                return 2

        @Mixin(XY)
        class XYMixin(Mixin.Interface):
            @inject_at("target", InjectionPosition.ALL_RETURN)
            def target(self):
                global FLAG
                FLAG = True

        global FLAG
        FLAG = False

        XY.target(None)

        self.assertFalse(FLAG)

        XYMixin._apply()

        XY.target(None)

        self.assertTrue(FLAG)

        FLAG = False

    def test_name_copy(self):
        class XY:
            def target(self):
                a = 0
                return 2

        @Mixin(XY)
        class XYMixin(Mixin.Interface):
            @inject_at("target", InjectionPosition.HEAD)
            def target(self):
                global FLAG
                FLAG = True

        global FLAG
        FLAG = False

        XY.target(None)

        self.assertFalse(FLAG)

        XYMixin._apply()

        XY.target(None)

        self.assertTrue(FLAG)

        FLAG = False
