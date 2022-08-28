from unittest import TestCase
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction


class TestMutableFunction(TestCase):
    def test_simple_decode(self):
        def target():
            pass

        mut = MutableFunction(target)
        self.assertEqual([Instruction("LOAD_CONST", None), Instruction("RETURN_VALUE")], mut.instructions)

    def test_reassemble(self):
        def target():
            pass

        mut = MutableFunction(target)
        mut.decode_instructions()
        mut.assemble_fast(mut.instructions)
        mut.raw_code = mut.raw_code

        self.assertEqual([Instruction("LOAD_CONST", None), Instruction("RETURN_VALUE")], mut.instructions)

