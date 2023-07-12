from unittest import TestCase

from bytecodemanipulation.assembler.target import apply_operations
from bytecodemanipulation.assembler.target import assembly
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import ConstantAccessExpression
from bytecodemanipulation.data.shared.expressions.LocalAccessExpression import LocalAccessExpression

from bytecodemanipulation.data.shared.expressions.AttributeAccessExpression import AttributeAccessExpression

from bytecodemanipulation.data.shared.expressions.CompoundExpression import CompoundExpression
from bytecodemanipulation.data.shared.instructions.LoadAssembly import LoadAssembly


class TestParser(TestCase):
    def test_repr(self):
        tree = Parser("LOAD $test.x -> $test").parse()
        self.assertEqual(repr(tree), "Compound(LOAD($!'test'.x, $!'test'))")

    def test_copy(self):
        tree = Parser("LOAD $test.x -> $test").parse()
        self.assertEqual(tree, tree.copy())

    def test_visit_parts(self):
        tree = Parser("LOAD $test.x -> $test").parse()

        visited = False

        def visitor(obj, children, parents):
            if isinstance(obj, AttributeAccessExpression):
                nonlocal visited
                visited = True

        tree.visit_parts(visitor, [])
        self.assertTrue(visited)

    def test_simple_load(self):
        tree = Parser("LOAD $test.x -> $test").parse()
        self.assertEqual(
            CompoundExpression(
                [
                    LoadAssembly(
                        AttributeAccessExpression(
                            LocalAccessExpression(
                                "test",
                            ),
                            "x",
                        ),
                        LocalAccessExpression(
                            "test",
                        ),
                    )
                ]
            ),
            tree,
        )

    def test_simple_store(self):
        tree = Parser("LOAD 10 -> $test.x").parse()
        self.assertEqual(
            CompoundExpression(
                [
                    LoadAssembly(
                        ConstantAccessExpression(10),
                        AttributeAccessExpression(
                            LocalAccessExpression(
                                "test",
                            ),
                            "x",
                        ),
                    )
                ]
            ),
            tree,
        )

    def test_missing_identifier_in_load(self):
        try:
            Parser("LOAD $test. -> $test").parse()
        except PropagatingCompilerException as e:
            self.assertEqual(e.args, ("expected <identifier> or &<identifier>",))
        else:
            self.fail()

    def test_missing_identifier_in_store(self):
        try:
            Parser("LOAD 10 -> $test.").parse()
        except PropagatingCompilerException as e:
            self.assertEqual(e.args, ("expected <identifier> or &<identifier>",))
        else:
            self.fail()


class MockObject:
    def __init__(self, value=None):
        self.value = value


class TestAssembly(TestCase):
    def test_simple_load(self):
        @apply_operations
        def target(x):
            assembly("RETURN $x.value")

        self.assertEqual(target(MockObject(10)), 10)

    def test_simple_store(self):
        @apply_operations
        def target(x):
            assembly("LOAD 10 -> $x.value")

        mock = MockObject()
        target(mock)
        self.assertEqual(mock.value, 10)

    def test_try_eval_static(self):
        def target(x):
            assembly("ASSERT_STATIC $x.value")

        try:
            apply_operations(target, unwrap_exceptions=False)
        except PropagatingCompilerException as e:
            self.assertEqual(e.args, ("Expected <static evaluate-able> at 'expression', got 'AttributeAccessExpression' as type",))
        else:
            self.fail()
