import dis

from bytecodemanipulation.CodeOptimiser import optimise_code

from bytecodemanipulation.util import Opcodes

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

from bytecodemanipulation.OptimiserAnnotations import builtins_are_static, name_is_static, returns_argument, constant_operation, run_optimisations
from unittest import TestCase


@constant_operation()
def test(a: int):
    return a + 10


class TestSet1(TestCase):
    def setUp(self) -> None:
        run_optimisations()

    def tearDown(self) -> None:
        run_optimisations()

    def test_function_eval(self):
        @builtins_are_static()
        @name_is_static("test", lambda: test)
        def target():
            return test(min(1, 2))

        self.assertEqual(target(), 11)

        run_optimisations()

        self.assertEqual(target(), 11)

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 11)

        # Result is a "return 11" function

    def test_subtract(self):
        @builtins_are_static()
        @name_is_static("test", lambda: test)
        def target():
            return test(1) - test(-2)

        self.assertEqual(target(), 3)

        run_optimisations()

        dis.dis(target)

        self.assertEqual(target(), 3)

        helper = BytecodePatchHelper(target)

        # Remove NOP's we might have left
        optimise_code(helper)

        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 3)

    # def test_complex_eval(self):
    #     @builtins_are_static()
    #     @name_is_static("test", lambda: test)
    #     def target():
    #         return test(test(test(1) - test(-2)) * test(0)) // test(4)
    #
    #     self.assertEqual(target(), 10)
    #
    #     run_optimisations()
    #
    #     dis.dis(target)
    #
    #     self.assertEqual(target(), 10)
    #
    #     helper = BytecodePatchHelper(target)
    #     self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
    #     self.assertEqual(helper.instruction_listing[0].argval, 10)
