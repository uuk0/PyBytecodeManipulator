import dis
from unittest import TestCase
from bytecodemanipulation.MutableFunction import MutableFunction, Instruction


class TestMutableFunction(TestCase):
    def test_simple_decode(self):
        def target():
            pass

        mut = MutableFunction(target)
        self.assertEqual(
            [
                Instruction(None, 0, "LOAD_CONST", None),
                Instruction(None, 1, "RETURN_VALUE"),
            ],
            mut.instructions,
        )

    def test_reassemble(self):
        def target():
            pass

        mut = MutableFunction(target)
        mut.decode_instructions()
        mut.assemble_fast(mut.instructions)
        # mut.raw_code = mut.raw_code

        self.assertEqual(
            [
                Instruction(None, 0, "LOAD_CONST", None),
                Instruction(None, 1, "RETURN_VALUE"),
            ],
            mut.instructions,
        )

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
        mut.assemble_instructions_from_tree(mut.instructions[0].optimise_tree())

    def test_reassign(self):
        def target():
            return "test"

        mut = MutableFunction(target)
        mut.instructions = mut.instructions
        mut.reassign_to_function()

        self.assertEqual(target(), "test")
