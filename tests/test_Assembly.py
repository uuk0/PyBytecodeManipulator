import dis
import itertools
import typing
from unittest import TestCase


from bytecodemanipulation import data_loader

data_loader.INIT_ASSEMBLY = False
from bytecodemanipulation.assembler.Parser import *
from bytecodemanipulation.assembler.target import assembly, label, jump as asm_jump
from bytecodemanipulation.assembler.Emitter import apply_inline_assemblies

try:
    from code_parser.parsers.common import IdentifierExpression
    from code_parser.lexers.common import IdentifierToken
except ImportError:
    from bytecodemanipulation.assembler.util.parser import IdentifierExpression
    from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken

data_loader.load_assembly_instructions()


if typing.TYPE_CHECKING:
    from bytecodemanipulation.data.v3_10.assembly_instructions import *

from bytecodemanipulation.optimiser_util import remove_nops, inline_const_value_pop_pairs
from tests.test_issues import compare_optimized_results


globals().update(data_loader.ASSEMBLY_MODULE)


GLOBAL = None


class TestParser(TestCase):
    def assertEqualList(
        self, correct: CompoundExpression, to_check: CompoundExpression
    ):
        if len(correct.children) != len(to_check.children):
            for check, corr in itertools.zip_longest(correct.children, to_check.children):
                print(f"Expected {corr}, got {check}")

        self.assertEqual(
            len(correct.children), len(to_check.children), "Length of lists!"
        )

        for a, b in zip(correct.children, to_check.children):
            self.assertEqual(a, b)

    def test_load_global(self):
        expr = Parser(
            "LOAD_GLOBAL test\nLOAD_GLOBAL 10\nLOAD_GLOBAL @test\nLOAD_GLOBAL @10\nLOAD_GLOBAL @hello -> $test"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    LoadGlobalAssembly("test"),
                    LoadGlobalAssembly(10),
                    LoadGlobalAssembly("test"),
                    LoadGlobalAssembly(10),
                    LoadGlobalAssembly("hello", LocalAccessExpression("test")),
                ]
            ),
            expr,
        )

    def test_store_global(self):
        expr = Parser(
            "STORE_GLOBAL test\nSTORE_GLOBAL @test\nSTORE_GLOBAL test (@test)\nSTORE_GLOBAL test ($test)\nSTORE_GLOBAL test (%)"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    StoreGlobalAssembly(IdentifierToken("test")),
                    StoreGlobalAssembly(IdentifierToken("test")),
                    StoreGlobalAssembly(
                        IdentifierToken("test"),
                        GlobalAccessExpression(IdentifierToken("test")),
                    ),
                    StoreGlobalAssembly(
                        IdentifierToken("test"),
                        LocalAccessExpression(IdentifierToken("test")),
                    ),
                    StoreGlobalAssembly(
                        IdentifierToken("test"), TopOfStackAccessExpression()
                    ),
                ]
            ),
            expr,
        )

    def test_load_fast(self):
        expr = Parser(
            "LOAD_FAST test\nLOAD_FAST 10\nLOAD_FAST $test\nLOAD_FAST $10\nLOAD_FAST test -> @test"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    LoadFastAssembly("test"),
                    LoadFastAssembly(10),
                    LoadFastAssembly("test"),
                    LoadFastAssembly(10),
                    LoadFastAssembly("test", GlobalAccessExpression("test")),
                ]
            ),
            expr,
        )

    def test_store_fast(self):
        expr = Parser(
            "STORE_FAST test\nSTORE_FAST $test\nSTORE_FAST test (@test)\nSTORE_FAST test ($test)\nSTORE_FAST test (%)"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    StoreFastAssembly("test"),
                    StoreFastAssembly("test"),
                    StoreFastAssembly("test", GlobalAccessExpression("test")),
                    StoreFastAssembly("test", LocalAccessExpression("test")),
                    StoreFastAssembly("test", TopOfStackAccessExpression()),
                ]
            ),
            expr,
        )

    def test_load_const(self):
        expr = Parser(
            'LOAD_CONST 10\nLOAD_CONST "Hello World!"\nLOAD_CONST 10 -> @test\nLOAD_CONST @global\nLOAD_CONST @global -> $test'
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    LoadConstAssembly(10),
                    LoadConstAssembly("Hello World!"),
                    LoadConstAssembly(10, GlobalAccessExpression("test")),
                    LoadConstAssembly(GlobalAccessExpression("global")),
                    LoadConstAssembly(
                        GlobalAccessExpression("global"), LocalAccessExpression("test")
                    ),
                ]
            ),
            expr,
        )

    def test_load(self):
        expr = Parser(
            'LOAD @test\nLOAD $test\nLOAD @global[10]\nLOAD $local[20]\nLOAD "hello"\nLOAD @test -> $hello\nLOAD @!test'
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    LoadAssembly(GlobalAccessExpression("test")),
                    LoadAssembly(LocalAccessExpression("test")),
                    LoadAssembly(
                        SubscriptionAccessExpression(
                            GlobalAccessExpression("global"),
                            ConstantAccessExpression(10),
                        )
                    ),
                    LoadAssembly(
                        SubscriptionAccessExpression(
                            LocalAccessExpression("local"), ConstantAccessExpression(20)
                        )
                    ),
                    LoadAssembly(ConstantAccessExpression("hello")),
                    LoadAssembly(
                        GlobalAccessExpression("test"), LocalAccessExpression("hello")
                    ),
                    LoadAssembly(GlobalStaticAccessExpression("test")),
                ]
            ),
            expr,
        )

    def test_store(self):
        expr = Parser(
            "STORE @test\nSTORE $test\nSTORE @global[10]\nSTORE $local[20]"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    StoreAssembly(GlobalAccessExpression("test")),
                    StoreAssembly(LocalAccessExpression("test")),
                    StoreAssembly(
                        SubscriptionAccessExpression(
                            GlobalAccessExpression("global"), IntegerToken("10")
                        )
                    ),
                    StoreAssembly(
                        SubscriptionAccessExpression(
                            LocalAccessExpression("local"), IntegerToken("20")
                        )
                    ),
                ]
            ),
            expr,
        )

        expr = Parser(
            "STORE @test ($test)\nSTORE $test (@global)\nSTORE @global[10] ($local[10])"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    StoreAssembly(
                        GlobalAccessExpression("test"), LocalAccessExpression("test")
                    ),
                    StoreAssembly(
                        LocalAccessExpression("test"), GlobalAccessExpression("global")
                    ),
                    StoreAssembly(
                        SubscriptionAccessExpression(
                            GlobalAccessExpression("global"), IntegerToken("10")
                        ),
                        SubscriptionAccessExpression(
                            LocalAccessExpression("local"), IntegerToken("10")
                        ),
                    ),
                ]
            ),
            expr,
        )

    def test_call(self):
        expr = Parser(
            """
CALL @print ("Hello World!")
CALL @print ("Hello World!",) -> $result
CALL @print ("Hello World!", "test") -> $result
CALL $print[@test] (@test, @hello) -> %
CALL @test (key=@value) -> @result
CALL @test ($direct, key=@value) -> @result
CALL @test ($direct.test, key=@value) -> @result
CALL @test.x (*$x, @b, *%)
"""
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    CallAssembly(
                        GlobalAccessExpression("print"),
                        [CallAssembly.Arg(ConstantAccessExpression("Hello World!"))],
                    ),
                    CallAssembly(
                        GlobalAccessExpression("print"),
                        [CallAssembly.Arg(ConstantAccessExpression("Hello World!"))],
                        LocalAccessExpression("result"),
                    ),
                    CallAssembly(
                        GlobalAccessExpression("print"),
                        [
                            CallAssembly.Arg(ConstantAccessExpression("Hello World!")),
                            CallAssembly.Arg(ConstantAccessExpression("test")),
                        ],
                        LocalAccessExpression("result"),
                    ),
                    CallAssembly(
                        SubscriptionAccessExpression(
                            LocalAccessExpression("print"),
                            GlobalAccessExpression("test"),
                        ),
                        [
                            CallAssembly.Arg(GlobalAccessExpression("test")),
                            CallAssembly.Arg(GlobalAccessExpression("hello")),
                        ],
                        TopOfStackAccessExpression(),
                    ),
                    CallAssembly(
                        GlobalAccessExpression("test"),
                        [CallAssembly.KwArg("key", GlobalAccessExpression("value"))],
                        GlobalAccessExpression("result"),
                    ),
                    CallAssembly(
                        GlobalAccessExpression("test"),
                        [
                            CallAssembly.Arg(LocalAccessExpression("direct")),
                            CallAssembly.KwArg("key", GlobalAccessExpression("value")),
                        ],
                        GlobalAccessExpression("result"),
                    ),
                    CallAssembly(
                        GlobalAccessExpression("test"),
                        [
                            CallAssembly.Arg(
                                AttributeAccessExpression(
                                    LocalAccessExpression("direct"), "test"
                                )
                            ),
                            CallAssembly.KwArg("key", GlobalAccessExpression("value")),
                        ],
                        GlobalAccessExpression("result"),
                    ),
                    CallAssembly(
                        AttributeAccessExpression(GlobalAccessExpression("test"), "x"),
                        [
                            CallAssembly.StarArg(LocalAccessExpression("x")),
                            CallAssembly.Arg(GlobalAccessExpression("b")),
                            CallAssembly.StarArg(TopOfStackAccessExpression()),
                        ],
                    ),
                ]
            ),
            expr,
        )

    def test_binary_operator(self):
        expr = Parser(
            """
OP @lhs + @rhs -> @result
OP @lhs[$local.attr] ** @rhs"""
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    OpAssembly(
                        OpAssembly.BinaryOperation(
                            GlobalAccessExpression("lhs"),
                            "+",
                            GlobalAccessExpression("rhs"),
                        ),
                        GlobalAccessExpression("result"),
                    ),
                    OpAssembly(
                        OpAssembly.BinaryOperation(
                            SubscriptionAccessExpression(
                                GlobalAccessExpression("lhs"),
                                AttributeAccessExpression(
                                    LocalAccessExpression("local"), "attr"
                                ),
                            ),
                            "**",
                            GlobalAccessExpression("rhs"),
                        )
                    ),
                ]
            ),
            expr,
        )

    def test_pop(self):
        expr = Parser("POP\nPOP 10").parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    PopElementAssembly(IntegerToken("1")),
                    PopElementAssembly(IntegerToken("10")),
                ]
            ),
            expr,
        )

    def test_return(self):
        expr = Parser("RETURN\nRETURN @global").parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    ReturnAssembly(),
                    ReturnAssembly(GlobalAccessExpression("global")),
                ]
            ),
            expr,
        )

    def test_yield(self):
        expr = Parser("YIELD\nYIELD @global\nYIELD *\nYIELD* $local\nYIELD -> %\nYIELD @global -> $local\n YIELD* -> @global\nYIELD* @global -> $local").parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    YieldAssembly(),
                    YieldAssembly(GlobalAccessExpression("global")),
                    YieldAssembly(is_star=True),
                    YieldAssembly(LocalAccessExpression("local"), is_star=True),
                    YieldAssembly(target=TopOfStackAccessExpression()),
                    YieldAssembly(GlobalAccessExpression("global"), target=LocalAccessExpression("local")),
                    YieldAssembly(is_star=True, target=GlobalAccessExpression("global")),
                    YieldAssembly(GlobalAccessExpression("global"), True, LocalAccessExpression("local")),
                ]
            ),
            expr,
        )

    def test_if_expr(self):
        expr = Parser(
            """
IF @global {
}

IF $local {
    STORE @global
}

IF OP ($a == $b) {
    STORE @global
}

"""
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    IFAssembly(
                        GlobalAccessExpression("global"), CompoundExpression([])
                    ),
                    IFAssembly(
                        LocalAccessExpression("local"),
                        CompoundExpression(
                            [StoreAssembly(GlobalAccessExpression("global"))]
                        ),
                    ),
                    IFAssembly(
                        OpAssembly(
                            OpAssembly.BinaryOperation(
                                LocalAccessExpression("a"),
                                "==",
                                LocalAccessExpression("b"),
                            )
                        ),
                        CompoundExpression(
                            [StoreAssembly(GlobalAccessExpression("global"))]
                        ),
                    ),
                ]
            ),
            expr,
        )

    def test_while_expr(self):
        expr = Parser(
            """
WHILE @global {
}

WHILE $local {
    STORE @global
}

WHILE OP ($a == $b) {
    STORE @global
}

"""
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    WHILEAssembly(
                        GlobalAccessExpression("global"), CompoundExpression([])
                    ),
                    WHILEAssembly(
                        LocalAccessExpression("local"),
                        CompoundExpression(
                            [StoreAssembly(GlobalAccessExpression("global"))]
                        ),
                    ),
                    WHILEAssembly(
                        OpAssembly(
                            OpAssembly.BinaryOperation(
                                LocalAccessExpression("a"),
                                "==",
                                LocalAccessExpression("b"),
                            )
                        ),
                        CompoundExpression(
                            [StoreAssembly(GlobalAccessExpression("global"))]
                        ),
                    ),
                ]
            ),
            expr,
        )

    def test_jump(self):
        expr = Parser("LABEL test\nJUMP test").parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    LabelAssembly("test"),
                    JumpAssembly("test"),
                ]
            ),
            expr,
        )


class TestInlineAssembly(TestCase):
    def test_empty(self):
        def target():
            assembly("")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: None, opt_ideal=2)

    def test_simple(self):
        def target():
            assembly("LOAD @print; POP")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        def compare():
            print

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_return(self):
        def target():
            assembly("RETURN 10")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: 10, opt_ideal=2)

    def test_jump(self):
        def target(x):
            assembly("JUMP test")
            if x:
                return 4
            label("test")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: None)

    def test_jump_in_assembly(self):
        def target(x):
            assembly("JUMP test\nRETURN 0\nLABEL test")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: None)

    def test_jump_across_assembly_blocks(self):
        def target(x):
            assembly("JUMP test\nRETURN 0")
            assembly("LABEL test")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: None)

    def test_jump_method(self):
        def target():
            asm_jump("test")
            print("Hello World")
            label("test")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: None)

    def test_conditional_jump(self):
        def target(x):
            assembly("JUMP test IF @GLOBAL\nRETURN 0\nLABEL test")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: 0 if not GLOBAL else None)

    def test_conditional_jump_external_target(self):
        def target(x):
            assembly("JUMP test IF @GLOBAL\nRETURN 0")
            label("test")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, lambda: 0 if not GLOBAL else None)

    def test_yield(self):
        def target(x):
            assembly("""
YIELD @GLOBAL
YIELD* @GLOBAL
YIELD* @GLOBAL -> $t
YIELD @GLOBAL -> $v""")
            yield 0

        def compare():
            yield GLOBAL
            yield from GLOBAL
            t = (yield from GLOBAL)
            v = (yield GLOBAL)
            yield 0

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, compare, opt_ideal=2)


