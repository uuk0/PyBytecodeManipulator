import dis
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

    def test_complex_tree_reassemble(self):
        def target(a):
            if a:
                b = 0
                while b:
                    a += 1
                    b = a / b

            elif "a" in "ab":
                pass
            else:
                return False

            return True

        mut = MutableFunction(target)
        mut.instructions[0].optimise_tree()
        mut.assemble_instructions_from_tree(mut.instructions[0])

    def test_reassign(self):
        def target():
            return "test"

        mut = MutableFunction(target)
        mut.instructions = mut.instructions
        mut.reassign_to_function()

        self.assertEqual(target(), "test")

