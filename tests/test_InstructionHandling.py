from unittest import TestCase

from .test_space import create_big_function


class TestBigFunctions(TestCase):
    def test_extended_indices_1(self):
        from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

        func = create_big_function()
        helper = BytecodePatchHelper(func)
        helper.replaceConstant(0, 1)
        helper.store()
        helper.patcher.applyPatches()
        func()
