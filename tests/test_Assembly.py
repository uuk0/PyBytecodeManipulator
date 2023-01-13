from unittest import TestCase
from bytecodemanipulation.assembler.Parser import *
from code_parser.parsers.common import IdentifierExpression
from code_parser.lexers.common import IdentifierToken


class TestParser(TestCase):
    def test_load_global(self):
        expr = Parser("LOAD_GLOBAL test\nLOAD_GLOBAL 10\nLOAD_GLOBAL @test\nLOAD_GLOBAL @10\nLOAD_GLOBAL @hello -> $test").parse()

        self.assertEqual(
            CompoundExpression([
                LoadGlobalAssembly("test"),
                LoadGlobalAssembly(10),
                LoadGlobalAssembly("test"),
                LoadGlobalAssembly(10),
                LoadGlobalAssembly("hello", LocalAccessExpression("test"))
            ]),
            expr
        )

    def test_store_global(self):
        expr = Parser("STORE_GLOBAL test\nSTORE_GLOBAL @test\nSTORE_GLOBAL test (@test)\nSTORE_GLOBAL test ($test)\nSTORE_GLOBAL test (%)").parse()

        self.assertEqual(
            CompoundExpression([
                StoreGlobalAssembly(IdentifierToken("test")),
                StoreGlobalAssembly(IdentifierToken("test")),
                StoreGlobalAssembly(IdentifierToken("test"), GlobalAccessExpression(IdentifierToken("test"))),
                StoreGlobalAssembly(IdentifierToken("test"), LocalAccessExpression(IdentifierToken("test"))),
                StoreGlobalAssembly(IdentifierToken("test"), TopOfStackAccessExpression()),
            ]),
            expr
        )

    def test_load_fast(self):
        expr = Parser("LOAD_FAST test\nLOAD_FAST 10\nLOAD_FAST $test\nLOAD_FAST $10\nLOAD_FAST test -> @test").parse()

        self.assertEqual(
            CompoundExpression([
                LoadFastAssembly("test"),
                LoadFastAssembly(10),
                LoadFastAssembly("test"),
                LoadFastAssembly(10),
                LoadFastAssembly("test", GlobalAccessExpression("test")),
            ]),
            expr
        )

    def test_store_fast(self):
        expr = Parser("STORE_FAST test\nSTORE_FAST $test\nSTORE_FAST test (@test)\nSTORE_FAST test ($test)\nSTORE_FAST test (%)").parse()

        self.assertEqual(
            CompoundExpression([
                StoreFastAssembly("test"),
                StoreFastAssembly("test"),
                StoreFastAssembly("test", GlobalAccessExpression("test")),
                StoreFastAssembly("test", LocalAccessExpression("test")),
                StoreFastAssembly("test", TopOfStackAccessExpression()),
            ]),
            expr
        )

    def test_load_const(self):
        expr = Parser("LOAD_CONST 10\nLOAD_CONST \"Hello World!\"\nLOAD_CONST 10 -> @test\nLOAD_CONST @global\nLOAD_CONST @global -> $test").parse()

        self.assertEqual(
            CompoundExpression([
                LoadConstAssembly(10),
                LoadConstAssembly("Hello World!"),
                LoadConstAssembly(10, GlobalAccessExpression("test")),
                LoadConstAssembly(GlobalAccessExpression("global")),
                LoadConstAssembly(GlobalAccessExpression("global"), LocalAccessExpression("test")),
            ]),
            expr
        )

    def test_load(self):
        expr = Parser("LOAD @test\nLOAD $test\nLOAD @global[10]\nLOAD $local[20]\nLOAD \"hello\"\nLOAD @test -> $hello").parse()

        self.assertEqual(
            CompoundExpression([
                LoadAssembly(GlobalAccessExpression("test")),
                LoadAssembly(LocalAccessExpression("test")),
                LoadAssembly(SubscriptionAccessExpression(GlobalAccessExpression("global"), ConstantAccessExpression(10))),
                LoadAssembly(SubscriptionAccessExpression(LocalAccessExpression("local"), ConstantAccessExpression(20))),
                LoadAssembly(ConstantAccessExpression("hello")),
                LoadAssembly(GlobalAccessExpression("test"), LocalAccessExpression("hello")),
            ]),
            expr
        )

    def test_store(self):
        expr = Parser("STORE @test\nSTORE $test\nSTORE @global[10]\nSTORE $local[20]").parse()

        self.assertEqual(
            CompoundExpression([
                StoreAssembly(GlobalAccessExpression("test")),
                StoreAssembly(LocalAccessExpression("test")),
                StoreAssembly(SubscriptionAccessExpression(GlobalAccessExpression("global"), IntegerToken("10"))),
                StoreAssembly(SubscriptionAccessExpression(LocalAccessExpression("local"), IntegerToken("20"))),
            ]),
            expr
        )

        expr = Parser("STORE @test ($test)\nSTORE $test (@global)\nSTORE @global[10] ($local[10])").parse()

        self.assertEqual(
            CompoundExpression([
                StoreAssembly(GlobalAccessExpression("test"), LocalAccessExpression("test")),
                StoreAssembly(LocalAccessExpression("test"), GlobalAccessExpression("global")),
                StoreAssembly(SubscriptionAccessExpression(GlobalAccessExpression("global"), IntegerToken("10")), SubscriptionAccessExpression(LocalAccessExpression("local"), IntegerToken("10"))),
            ]),
            expr
        )

    def test_pop(self):
        expr = Parser("POP\nPOP 10").parse()

        self.assertEqual(
            CompoundExpression([
                PopElementAssembly(IntegerToken("1")),
                PopElementAssembly(IntegerToken("10")),
            ]),
            expr
        )

