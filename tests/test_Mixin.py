import unittest
from unittest import TestCase

from bytecodemanipulation.Mixin import *


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
