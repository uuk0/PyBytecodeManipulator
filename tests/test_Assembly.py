from unittest import TestCase

try:
    from bytecodemanipulation.assembler.Parser import *
    from code_parser.parsers.common import IdentifierExpression
    from code_parser.lexers.common import IdentifierToken
except ImportError:
    from bytecodemanipulation.assembler.util.parser import IdentifierExpression
    from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken


class TestParser(TestCase):
    def assertEqualList(self, correct: CompoundExpression, to_check: CompoundExpression):
        self.assertEqual(len(correct.children), len(to_check.children), "Length of lists!")

        for a, b in zip(correct.children, to_check.children):
            self.assertEqual(a, b)

    def test_load_global(self):
        expr = Parser("LOAD_GLOBAL test\nLOAD_GLOBAL 10\nLOAD_GLOBAL @test\nLOAD_GLOBAL @10\nLOAD_GLOBAL @hello -> $test").parse()

        self.assertEqualList(
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

        self.assertEqualList(
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

        self.assertEqualList(
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

        self.assertEqualList(
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

        self.assertEqualList(
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

        self.assertEqualList(
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

        self.assertEqualList(
            CompoundExpression([
                StoreAssembly(GlobalAccessExpression("test")),
                StoreAssembly(LocalAccessExpression("test")),
                StoreAssembly(SubscriptionAccessExpression(GlobalAccessExpression("global"), IntegerToken("10"))),
                StoreAssembly(SubscriptionAccessExpression(LocalAccessExpression("local"), IntegerToken("20"))),
            ]),
            expr
        )

        expr = Parser("STORE @test ($test)\nSTORE $test (@global)\nSTORE @global[10] ($local[10])").parse()

        self.assertEqualList(
            CompoundExpression([
                StoreAssembly(GlobalAccessExpression("test"), LocalAccessExpression("test")),
                StoreAssembly(LocalAccessExpression("test"), GlobalAccessExpression("global")),
                StoreAssembly(SubscriptionAccessExpression(GlobalAccessExpression("global"), IntegerToken("10")), SubscriptionAccessExpression(LocalAccessExpression("local"), IntegerToken("10"))),
            ]),
            expr
        )

    def test_call(self):
        expr = Parser("""
CALL @print ("Hello World!")
CALL @print ("Hello World!",) -> $result
CALL @print ("Hello World!", "test") -> $result
CALL $print[@test] (@test, @hello) -> %
CALL @test (key=@value) -> @result
CALL @test ($direct, key=@value) -> @result
CALL @test ($direct.test, key=@value) -> @result
""").parse()

        self.assertEqualList(
            CompoundExpression([
                CallAssembly(GlobalAccessExpression("print"), [CallAssembly.Arg(ConstantAccessExpression("Hello World!"))]),
                CallAssembly(GlobalAccessExpression("print"), [CallAssembly.Arg(ConstantAccessExpression("Hello World!"))], LocalAccessExpression("result")),
                CallAssembly(GlobalAccessExpression("print"), [CallAssembly.Arg(ConstantAccessExpression("Hello World!")), CallAssembly.Arg(ConstantAccessExpression("test"))], LocalAccessExpression("result")),
                CallAssembly(SubscriptionAccessExpression(LocalAccessExpression("print"), GlobalAccessExpression("test")), [CallAssembly.Arg(GlobalAccessExpression("test")), CallAssembly.Arg(GlobalAccessExpression("hello"))], TopOfStackAccessExpression()),
                CallAssembly(GlobalAccessExpression("test"), [CallAssembly.KwArg("key", GlobalAccessExpression("value"))], GlobalAccessExpression("result")),
                CallAssembly(GlobalAccessExpression("test"), [CallAssembly.Arg(LocalAccessExpression("direct")), CallAssembly.KwArg("key", GlobalAccessExpression("value"))], GlobalAccessExpression("result")),
                CallAssembly(GlobalAccessExpression("test"), [CallAssembly.Arg(AttributeAccessExpression(LocalAccessExpression("direct"), "test")), CallAssembly.KwArg("key", GlobalAccessExpression("value"))], GlobalAccessExpression("result")),
            ]),
            expr,
        )

    def test_pop(self):
        expr = Parser("POP\nPOP 10").parse()

        self.assertEqualList(
            CompoundExpression([
                PopElementAssembly(IntegerToken("1")),
                PopElementAssembly(IntegerToken("10")),
            ]),
            expr
        )

