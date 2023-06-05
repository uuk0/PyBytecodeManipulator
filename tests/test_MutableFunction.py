import dis
from unittest import TestCase
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class TestMutableFunction(TestCase):
    def test_simple_decode(self):
        def target():
            pass

        mut = MutableFunction(target)
        builder = mut.create_filled_builder()
        self.assertEqual(
            [
                Instruction(Opcodes.LOAD_CONST, None),
                Instruction(Opcodes.RETURN_VALUE),
            ],
            builder.temporary_instructions,
        )

    def test_reassemble(self):
        def target():
            pass

        mut = MutableFunction(target)
        mut.decode_instructions()
        builder = mut.create_filled_builder()
        # mut.raw_code = mut.raw_code

        self.assertEqual(
            [
                Instruction(Opcodes.LOAD_CONST, None),
                Instruction(Opcodes.RETURN_VALUE),
            ],
            builder.temporary_instructions,
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
        mut.create_filled_builder()

    def test_reassign(self):
        def target():
            return "test"

        mut = MutableFunction(target)
        mut.decode_instructions()
        mut.reassign_to_function()

        self.assertEqual(target(), "test")

    def test_exception_tables(self):
        def target():
            try:
                raise ValueError
            except ValueError:
                return 0
            return 1

        self.assertEqual(target(), 0)

        mut = MutableFunction(target)
        mut.decode_instructions()
        self.assertEqual(len(mut.exception_table.table), 1)
        mut.reassign_to_function()

        self.assertEqual(target(), 0)

