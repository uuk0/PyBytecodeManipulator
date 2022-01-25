import dis
from unittest import TestCase
from bytecodemanipulation import Emulator
from bytecodemanipulation.Emulator import InstructionExecutionException
from bytecodemanipulation.Emulator import StackUnderflowException
from bytecodemanipulation.MutableCodeObject import createInstruction
from bytecodemanipulation.MutableCodeObject import MutableCodeObject
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper


class TestEmulator(TestCase):
    def test_simple(self):
        def target():
            return 0

        self.assertEqual(target(), 0)
        self.assertEqual(Emulator.CURRENT.execute(target), 0)

    def test_control_flow(self):
        def target(flag: bool):
            if flag:
                return 243
            return 120

        self.assertEqual(target(False), 120)
        self.assertEqual(target(True), 243)

        self.assertEqual(Emulator.CURRENT.execute(target, False), 120)
        self.assertEqual(Emulator.CURRENT.execute(target, True), 243)

    def test_while_loop(self):
        def target():
            i = 0
            while i < 100:
                i += 1
            return i

        self.assertEqual(target(), 100)
        self.assertEqual(Emulator.CURRENT.execute(target), 100)

    def test_simple_for_loop(self):
        def target():
            x = 0
            for i in range(10):
                x -= i
            return x

        self.assertEqual(target(), -45)
        self.assertEqual(Emulator.CURRENT.execute(target), -45)


class TestEmulatorInjection(TestCase):
    def test_simple(self):
        def target():
            return 0

        previous = MutableCodeObject(target)
        helper = BytecodePatchHelper(target)
        helper.enable_verbose_exceptions()
        helper.store()
        helper.patcher.applyPatches()

        self.assertEqual(target(), 0)

        # And make sure that everything goes right
        new = MutableCodeObject(target)
        self.assertNotEqual(previous.code_string, new.code_string)

    def test_simple_crash(self):
        def target():
            return 0

        helper = BytecodePatchHelper(target)

        # This must create an StackUnderflowException, as the stack is empty at that time!
        helper.insertRegion(0, [createInstruction("POP_TOP")])

        helper.enable_verbose_exceptions()
        helper.store()
        helper.patcher.applyPatches()

        self.assertRaises(InstructionExecutionException, target)

    def test_simple_crash_twice_layer(self):
        def target():
            return 0

        helper = BytecodePatchHelper(target)

        # This must create an StackUnderflowException, as the stack is empty at that time!
        helper.insertRegion(0, [createInstruction("POP_TOP")])

        helper.enable_verbose_exceptions()
        helper.enable_verbose_exceptions(True)
        helper.store()
        helper.patcher.applyPatches()

        self.assertRaises(InstructionExecutionException, target)

    def test_control_flow(self):
        def target(flag: bool):
            if flag:
                return 243
            return 120

        self.assertEqual(target(False), 120)
        self.assertEqual(target(True), 243)

        helper = BytecodePatchHelper(target)
        helper.enable_verbose_exceptions()
        helper.store()
        helper.patcher.applyPatches()

        self.assertEqual(target(False), 120)
        self.assertEqual(target(True), 243)
