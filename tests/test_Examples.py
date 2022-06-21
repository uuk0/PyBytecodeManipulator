import dis

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

