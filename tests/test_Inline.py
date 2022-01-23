"""
mcpython - a minecraft clone written in python licenced under the MIT-licence
(https://github.com/mcpython4-coding/core)

Contributors: uuk, xkcdjerry (inactive)

Based on the game of fogleman (https://github.com/fogleman/Minecraft), licenced under the MIT-licence
Original game "minecraft" by Mojang Studios (www.minecraft.net), licenced under the EULA
(https://account.mojang.com/documents/minecraft_eula)
Mod loader inspired by "Minecraft Forge" (https://github.com/MinecraftForge/MinecraftForge) and similar

This project is not official by mojang and does not relate to it.
"""
import dis

from bytecodemanipulation.InstructionMatchers import CounterMatcher
from bytecodemanipulation.util import Opcodes
from unittest import TestCase
from bytecodemanipulation.BytecodeProcessors import MethodInlineProcessor
from bytecodemanipulation.TransformationHelper import MixinPatchHelper


TEST_TARGET = 0


class TestInline(TestCase):
    def setUp(self):
        global TEST_TARGET
        TEST_TARGET = 0

    def test_simple(self):
        def a():
            b()

        def b():
            global TEST_TARGET
            TEST_TARGET += 1

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        a()
        self.assertEqual(TEST_TARGET, 1)

    def test_two_method_inline(self):
        def a():
            b()
            b()

        def b():
            global TEST_TARGET
            TEST_TARGET += 1

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        a()
        self.assertEqual(TEST_TARGET, 2)

    def test_parameter_redirect(self):
        def a(p: int):
            b(p)

        def b(p: int):
            global TEST_TARGET
            TEST_TARGET += p

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        a(2)
        self.assertEqual(TEST_TARGET, 2)

    def test_parameter_redirect_twice(self):
        def a(p: int):
            b(p)
            b(p - 1)

        def b(p: int):
            global TEST_TARGET
            TEST_TARGET += p

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        a(2)
        self.assertEqual(TEST_TARGET, 3)

    def test_parameter_redirect_twice_inline_one(self):
        def a(p: int):
            b(p)
            b(p - 1)

        def b(p: int):
            global TEST_TARGET
            TEST_TARGET += p

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor(
            "b", target_accessor=lambda: b, matcher=CounterMatcher(1)
        )
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        # If we inline correctly, this should remain in the old state
        self.assertEqual(helper.instruction_listing[14].opcode, Opcodes.CALL_FUNCTION)

        a(2)
        self.assertEqual(TEST_TARGET, 3)

    def test_parameter_redirect_keyword_args(self):
        def a(p: int):
            b(p - 1, 2)

        def b(p: int, q: int = 0):
            global TEST_TARGET
            TEST_TARGET += p * q

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        a(2)
        self.assertEqual(TEST_TARGET, 2)

    def test_parameter_redirect_keyword_args_twice(self):
        def a(p: int):
            b(p - 1)
            b(p - 1, 2)

        def b(p: int, q: int = 0):
            global TEST_TARGET
            TEST_TARGET += p * q

        dis.dis(a)

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        dis.dis(a)

        a(2)
        self.assertEqual(TEST_TARGET, 2)

    async def test_async_inline_simple(self):
        async def a():
            await b()

        async def b():
            global TEST_TARGET
            TEST_TARGET += 1

        helper = MixinPatchHelper(a)
        processor = MethodInlineProcessor("b", target_accessor=lambda: b)
        processor.apply(None, helper.patcher, helper)
        helper.store()
        helper.patcher.applyPatches()

        dis.dis(a)

        await a()
        self.assertEqual(TEST_TARGET, 1)
