from unittest import TestCase

from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import ConstantAccessExpression
from bytecodemanipulation.data.shared.expressions.LocalAccessExpression import LocalAccessExpression

from bytecodemanipulation.data.shared.expressions.AttributeAccessExpression import AttributeAccessExpression

from bytecodemanipulation.data.shared.expressions.CompoundExpression import CompoundExpression
from bytecodemanipulation.data.shared.instructions.AssertAssembly import AbstractAssertAssembly

from bytecodemanipulation.assembler.target import apply_operations
from bytecodemanipulation.assembler.target import assembly
from bytecodemanipulation.assembler.Parser import Parser


class TestParser(TestCase):
    def test_simple(self):
        expr = Parser("ASSERT $x").parse()

        self.assertEqual(expr, CompoundExpression(AbstractAssertAssembly.IMPLEMENTATION(LocalAccessExpression("x"))))

    def test_simple_with_message(self):
        expr = Parser("ASSERT $x \"test\"").parse()

        self.assertEqual(expr, CompoundExpression(AbstractAssertAssembly.IMPLEMENTATION(LocalAccessExpression("x"), ConstantAccessExpression("test"))))

    def test_repr(self):
        self.assertEqual(repr(Parser("ASSERT $x").parse()), "Compound(ASSERT($!'x', None))")

    def test_copy(self):
        expr = Parser("ASSERT $x").parse()
        self.assertEqual(expr, expr.copy())

    def test_no_target(self):
        try:
            expr = Parser("ASSERT").parse()
        except PropagatingCompilerException as e:
            self.assertEqual(e.args, ('expected <expression> after ASSERT',))
        else:
            self.fail()


class TestAssembly(TestCase):
    def test_assert(self):
        @apply_operations
        def target(x):
            assembly(
                """
ASSERT $x
"""
            )

        target(1)
        self.assertRaises(AssertionError, lambda: target(0))

    def test_assert_with_message(self):
        @apply_operations
        def target(x):
            assembly(
                """
ASSERT $x \"Test Message\"
"""
            )

        target(1)
        self.assertRaises(AssertionError, lambda: target(0))

        try:
            target(0)
        except AssertionError as e:
            self.assertEqual(e.args, ("Test Message",))
        else:
            self.assertTrue(False)
