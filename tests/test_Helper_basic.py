import asyncio
import dis
import sys
import typing
import warnings

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper
from bytecodemanipulation.TransformationHelper import capture_local
from bytecodemanipulation.util import Opcodes
from unittest import TestCase
from . import test_space

INVOKED = 0


class TestBasicBytecodeHelpers(TestCase):
    def _callTestMethod(self, method):
        result = method()

        if isinstance(result, typing.Awaitable):
            result = asyncio.get_event_loop().run_until_complete(result)

        if result is not None:
            warnings.warn(f'It is deprecated to return a value!=None from a '
                          f'test case ({method})', DeprecationWarning, stacklevel=3)

    def test_special_method_1(self):
        from bytecodemanipulation.TransformationHelper import (
            BytecodePatchHelper,
        )

        def inject():
            global INVOKED
            INVOKED += capture_local("a")

        helper = BytecodePatchHelper(inject)

    def test_processor_static_method_call(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def localtest():
            return 0

        patcher = MutableCodeObject(localtest)
        helper = BytecodePatchHelper(patcher)
        helper.insertStaticMethodCallAt(
            0, "tests.test_space:test_for_invoke"
        )
        helper.store()
        patcher.applyPatches()

        count = test_space.INVOKED
        self.assertEqual(localtest(), 0)
        self.assertEqual(test_space.INVOKED, count + 1)
        test_space.INVOKED = 0

    def test_processor_static_method_call_twice(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def localtest():
            return 0

        patcher = MutableCodeObject(localtest)
        helper = BytecodePatchHelper(patcher)
        helper.insertStaticMethodCallAt(
            0, "tests.test_space:test_for_invoke"
        )
        helper.insertStaticMethodCallAt(
            0, "tests.test_space:test_for_invoke"
        )
        helper.store()
        patcher.applyPatches()

        count = test_space.INVOKED
        self.assertEqual(localtest(), 0)
        self.assertEqual(test_space.INVOKED, count + 2)
        test_space.INVOKED = 0

    async def test_processor_static_method_call_to_async(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        invoked = 0

        async def localtest():
            return 0

        async def inject():
            nonlocal invoked
            invoked += 1

        patcher = MutableCodeObject(localtest)
        helper = BytecodePatchHelper(patcher)
        helper.insertAsyncStaticMethodCallAt(0, inject)
        helper.store()
        patcher.applyPatches()

        self.assertEqual(await localtest(), 0)
        self.assertEqual(invoked, 1)

    async def test_processor_static_method_call_to_async_twice(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        invoked = 0

        async def localtest():
            return 0

        async def inject():
            nonlocal invoked
            invoked += 1

        patcher = MutableCodeObject(localtest)
        helper = BytecodePatchHelper(patcher)
        helper.insertAsyncStaticMethodCallAt(0, inject)
        helper.insertAsyncStaticMethodCallAt(0, inject)
        helper.store()
        patcher.applyPatches()

        self.assertEqual(await localtest(), 0)
        self.assertEqual(invoked, 2)

    async def test_processor_static_method_call_async_context(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        async def localtest():
            return 0

        patcher = MutableCodeObject(localtest)
        helper = BytecodePatchHelper(patcher)
        helper.insertStaticMethodCallAt(
            1, "tests.test_space:test_for_invoke"
        )
        helper.store()
        patcher.applyPatches()

        count = test_space.INVOKED
        self.assertEqual(await localtest(), 0)
        self.assertEqual(test_space.INVOKED, count + 1)
        test_space.INVOKED = 0

    async def test_processor_static_method_call_async_context_twice(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        async def localtest():
            return 0

        patcher = MutableCodeObject(localtest)
        helper = BytecodePatchHelper(patcher)
        helper.insertStaticMethodCallAt(
            1, "tests.test_space:test_for_invoke"
        )
        helper.insertStaticMethodCallAt(
            1, "tests.test_space:test_for_invoke"
        )
        helper.store()
        patcher.applyPatches()

        count = test_space.INVOKED
        self.assertEqual(await localtest(), 0)
        self.assertEqual(test_space.INVOKED, count + 2)
        test_space.INVOKED = 0

    def test_insertRegion_offset(self):
        from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

        def test():
            a = 0
            return a

        helper = BytecodePatchHelper(test)

        helper.insertRegion(
            1,
            [
                dis.Instruction(
                    "YIELD_VALUE", Opcodes.YIELD_VALUE, 0, 0, "", 0, 0, False
                )
            ],
        )

        self.assertEqual(helper.instruction_listing[1].opname, "YIELD_VALUE")

    def test_objectbound_call_1(self):
        class Test:
            HIT = False

            def target(self):
                self.HIT = self.HIT

            def hit(self):
                self.HIT = True

        helper = BytecodePatchHelper(Test.target)
        helper.insertObjectBoundMethodCall(0 if sys.version_info.major <= 3 and sys.version_info.minor < 11 else 1, "hit")
        helper.store()
        helper.patcher.applyPatches()

        obj = Test()
        obj.target()
        self.assertTrue(obj.HIT)

    def test_objectbound_call_static_1(self):
        class Test:
            HIT = False

            def target(self):
                self.HIT = self.HIT

            def hit(self):
                self.HIT = True
                print("Hello World")

        helper = BytecodePatchHelper(Test.target)
        helper.insertObjectBoundMethodCall(0 if sys.version_info.major <= 3 and sys.version_info.minor < 11 else 1, "hit", method_instance=Test.hit)
        helper.store()
        helper.patcher.applyPatches()

        obj = Test()
        obj.target()
        self.assertTrue(obj.HIT)
