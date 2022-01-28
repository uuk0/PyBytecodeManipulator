import dis
import time
from unittest import TestCase

from bytecodemanipulation.MutableCodeObject import createInstruction


class TestSelfModifyingCode(TestCase):
    def test_simple(self):
        """
        This test is for checking what effects it has to apply patches to a running function.
        The best case would be no effect, as of python 3.10, this is the case
        """

        from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

        def target():
            helper.insertRegion(
                len(helper.instruction_listing) - 2,
                [
                    helper.patcher.createLoadConst("False"),
                    createInstruction("RETURN_VALUE"),
                ],
            )
            helper.store()
            helper.patcher.applyPatches()
            # time.sleep(2)

        helper = BytecodePatchHelper(target)
        self.assertEqual(target(), None)

        helper.re_eval_instructions()

        self.assertEqual(helper.instruction_listing[-4].opname, "LOAD_CONST")
