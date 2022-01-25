import dis
from unittest import TestCase
from bytecodemanipulation import Emulator
from bytecodemanipulation.Emulator import StackUnderflowException
from bytecodemanipulation.MutableCodeObject import createInstruction
from bytecodemanipulation.MutableCodeObject import MutableCodeObject
from bytecodemanipulation.TransformationHelper import BytecodePatchHelper


class TestEmulator(TestCase):
    def test_simple(self):
        def target():
            return 0

        self.assertEqual(Emulator.CURRENT.execute(target), 0)


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

        self.assertRaises(StackUnderflowException, target)
