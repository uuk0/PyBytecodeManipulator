import unittest
from unittest import TestCase

from bytecodemanipulation.Mixin import *


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

    def test_function_inject(self):
        class XY:
            def target(self):
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
