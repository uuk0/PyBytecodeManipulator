import dis
from unittest import TestCase

from bytecodemanipulation.assembler.target import apply_operations
from bytecodemanipulation.assembler.target import assembly


class TestOperators(TestCase):
    def test_simple_and_true(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 and 1)""")

        self.assertTrue(target())

    def test_simple_and_false_lhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 and 1)""")

        self.assertFalse(target())

    def test_simple_and_false_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 and 0)""")

        self.assertFalse(target())

    def test_simple_and_false_lhs_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 and 0)""")

        self.assertFalse(target())

    def test_and_eval(self):
        @apply_operations
        def target(m):
            assembly("""RETURN OP ($m() and $m())""")

        i = 0

        def incr():
            nonlocal i
            i += 1
            return 1

        self.assertTrue(target(incr))
        self.assertEqual(i, 2)

    def test_and_short(self):
        @apply_operations
        def target(tar):
            assembly("""RETURN OP (0 and $tar())""")

        self.assertFalse(target(self.fail))

    def test_simple_nand_true(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 nand 1)""")

        self.assertFalse(target())

    def test_simple_nand_false_lhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 nand 1)""")

        self.assertTrue(target())

    def test_simple_nand_false_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 nand 0)""")

        self.assertTrue(target())

    def test_simple_nand_false_lhs_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 nand 0)""")

        self.assertTrue(target())

    def test_nand_eval(self):
        @apply_operations
        def target(m):
            assembly("""RETURN OP ($m() nand $m())""")

        i = 0

        def incr():
            nonlocal i
            i += 1
            return 1

        self.assertFalse(target(incr))
        self.assertEqual(i, 2)

    def test_nand_short(self):
        @apply_operations
        def target(tar):
            assembly("""RETURN OP (0 nand $tar())""")

        self.assertTrue(target(self.fail))

    def test_simple_or_true_true(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 or 1)""")

        self.assertTrue(target())

    def test_simple_or_false_lhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 or 1)""")

        self.assertTrue(target())

    def test_simple_or_false_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 or 0)""")

        self.assertTrue(target())

    def test_simple_or_false_lhs_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 or 0)""")

        self.assertFalse(target())

    def test_or_eval(self):
        @apply_operations
        def target(m):
            assembly("""RETURN OP ($m() or $m())""")

        i = 0

        def incr():
            nonlocal i
            i += 1
            return 0

        self.assertFalse(target(incr))
        self.assertEqual(i, 2)

    def test_or_short(self):
        @apply_operations
        def target(tar):
            assembly("""RETURN OP (1 or $tar())""")

        self.assertTrue(target(self.fail))

    def test_simple_nor_true_true(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 nor 1)""")

        self.assertFalse(target())

    def test_simple_nor_false_lhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 nor 1)""")

        self.assertFalse(target())

    def test_simple_nor_false_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 nor 0)""")

        self.assertFalse(target())

    def test_simple_nor_false_lhs_rhs(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 nor 0)""")

        self.assertTrue(target())

    def test_nor_eval(self):
        @apply_operations
        def target(m):
            assembly("""RETURN OP ($m() nor $m())""")

        i = 0

        def incr():
            nonlocal i
            i += 1
            return 0

        self.assertTrue(target(incr))
        self.assertEqual(i, 2)

    def test_nor_short(self):
        @apply_operations
        def target(tar):
            assembly("""RETURN OP (1 nor $tar())""")

        self.assertFalse(target(self.fail))

    def test_xor_1_1(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 xor 1)""")

        self.assertFalse(target())

    def test_xor_1_0(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 xor 0)""")

        self.assertTrue(target())

    def test_xor_0_1(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 xor 1)""")

        self.assertTrue(target())

    def test_xor_0_0(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 xor 0)""")

        self.assertFalse(target())

    def test_xnor_1_1(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 xnor 1)""")

        self.assertTrue(target())

    def test_xnor_1_0(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (1 xnor 0)""")

        self.assertFalse(target())

    def test_xnor_0_1(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 xnor 1)""")

        self.assertFalse(target())

    def test_xnor_0_0(self):
        @apply_operations
        def target():
            assembly("""RETURN OP (0 xnor 0)""")

        self.assertTrue(target())

    def test_walrus_operator_simple(self):
        @apply_operations
        def target():
            a = 0
            assembly("OP $a := 1 -> \\")
            return a

        self.assertEqual(target(), 1)

    def test_walrus_operator_inverse_simple(self):
        @apply_operations
        def target():
            a = 0
            assembly("OP 1 =: $a -> \\")
            return a

        self.assertEqual(target(), 1)

    def test_instanceof_operator_true(self):
        @apply_operations
        def target():
            assembly("RETURN OP (10 instanceof ~int)")

        self.assertTrue(target())

    def test_instanceof_operator_false(self):
        @apply_operations
        def target():
            assembly("RETURN OP (10 instanceof ~list)")

        self.assertFalse(target())

    def test_subclassof_operator_true(self):
        @apply_operations
        def target():
            assembly("RETURN OP (~int subclassof ~object)")

        self.assertTrue(target())

    def test_subclassof_operator_false(self):
        @apply_operations
        def target():
            assembly("RETURN OP (~int subclassof ~list)")

        self.assertFalse(target())

    def test_hasattr_operator_true(self):
        @apply_operations
        def target():
            assembly('RETURN OP ("test" hasattr "upper")')

        self.assertTrue(target())

    def test_hasattr_operator_false(self):
        @apply_operations
        def target():
            assembly('RETURN OP ("test" hasattr "uper")')

        self.assertFalse(target())

    def test_sum_operator_basic(self):
        @apply_operations
        def target():
            assembly("RETURN OP (sum (1, 1))")

        self.assertEqual(target(), 2)

    def test_sum_operator_advanced(self):
        @apply_operations
        def target(a):
            assembly("RETURN OP (sum ($a, $a, $a, $a))")

        self.assertEqual(target(2), 8)
