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

