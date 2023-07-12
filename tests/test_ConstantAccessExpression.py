from unittest import TestCase

from bytecodemanipulation.assembler.target import apply_operations
from bytecodemanipulation.assembler.target import assembly
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.expressions.LocalAccessExpression import LocalAccessExpression

from bytecodemanipulation.data.shared.expressions.ConstantAccessExpression import ConstantAccessExpression

from bytecodemanipulation.data.shared.expressions.CompoundExpression import CompoundExpression
from bytecodemanipulation.data.shared.instructions.LoadAssembly import LoadAssembly


class TestParsing(TestCase):
    def test_parse_string(self):
        expr = Parser("LOAD \"test\"").parse()

        self.assertEqual(expr, CompoundExpression([LoadAssembly(ConstantAccessExpression("test"))]))

    def test_parse_int(self):
        expr = Parser("LOAD 10").parse()

        self.assertEqual(expr, CompoundExpression([LoadAssembly(ConstantAccessExpression(10))]))

    def test_parse_none(self):
        expr = Parser("LOAD None").parse()

        self.assertEqual(expr, CompoundExpression([LoadAssembly(ConstantAccessExpression(None))]))

    def test_parse_false(self):
        expr = Parser("LOAD False").parse()

        self.assertEqual(expr, CompoundExpression([LoadAssembly(ConstantAccessExpression(False))]))

    def test_parse_true(self):
        expr = Parser("LOAD True").parse()

        self.assertEqual(expr, CompoundExpression([LoadAssembly(ConstantAccessExpression(True))]))

    def test_copy(self):
        expr = Parser("LOAD True").parse()
        self.assertEqual(expr, expr.copy())

