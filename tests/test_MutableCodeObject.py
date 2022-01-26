import dis
import sys
import unittest

from bytecodemanipulation.MutableCodeObject import MutableCodeObject
from unittest import TestCase


class TestMutableCodeObject(TestCase):
    @unittest.skipUnless(sys.version_info.major == 3 and sys.version_info.minor < 11, "used opcode is invalid since 3.11")
    def test_apply_patches_simple(self):

        value = 0

        class Test:
            def wadd(self, x, y=1):
                pow_n = 3
                result = (x + y) ** pow_n
                nonlocal value
                value = result

        # Create an object of that class so we can be sure that it updates existing object-binds
        test_obj = Test()

        test_obj.wadd(3, 1)
        self.assertEqual(value, 64)

        # Apply a small patch to the function, replacing the + with a - in the code
        obj = MutableCodeObject(Test.wadd)
        obj.code_string[12:13] = dis.opmap["BINARY_SUBTRACT"].to_bytes(
            1, byteorder="little"
        )
        obj.applyPatches()

        value = 0
        test_obj.wadd(3, 1)
        self.assertEqual(value, 1)

    def test_library_processor_with_constant(self):
        import PIL.Image

        def test():
            return 0

        replacement_code = bytearray(test.__code__.co_code)

        image = PIL.Image.new("RGBA", (10, 10))

        obj = MutableCodeObject(PIL.Image.Image.copy)
        replacement_code[1] = obj.ensureConstant(0)
        obj.code_string = replacement_code
        obj.applyPatches()

        self.assertEqual(image.copy(), 0)

    def test_body_replacement(self):
        def a():
            return 0

        def b():
            return 1

        self.assertEqual(a(), 0)

        obj = MutableCodeObject(a)
        obj.overrideFrom(MutableCodeObject(b))
        obj.applyPatches()

        self.assertEqual(a(), 1)
