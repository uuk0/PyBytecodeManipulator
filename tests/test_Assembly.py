from unittest import TestCase
from bytecodemanipulation.assembler.Parser import *
from code_parser.parsers.common import IdentifierExpression
from code_parser.lexers.common import IdentifierToken


class TestParser(TestCase):
    def test_load_global(self):
        expr = Parser("LOAD_GLOBAL test").parse()

        self.assertEqual(
            CompoundExpression([LoadGlobalAssembly(IdentifierToken("test"))]),
            expr
        )

    def test_load(self):
        expr = Parser("LOAD @test\nLOAD $test\nLOAD @global[10]\nLOAD $local[20]").parse()

        self.assertEqual(
            CompoundExpression([
                LoadAssembly(GlobalAccessExpression(IdentifierToken("test"))),
                LoadAssembly(LocalAccessExpression(IdentifierToken("test"))),
                LoadAssembly(SubscriptionAccessExpression(GlobalAccessExpression(IdentifierToken("global")), IntegerToken("10"))),
                LoadAssembly(SubscriptionAccessExpression(LocalAccessExpression(IdentifierToken("local")), IntegerToken("20"))),
            ]),
            expr
        )

    def test_pop(self):
        expr = Parser("POP\nPOP 10").parse()

        self.assertEqual(
            CompoundExpression([
                PopElementAssembly(IntegerToken("0")),
                PopElementAssembly(IntegerToken("10")),
            ]),
            expr
        )

