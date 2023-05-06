import functools
from unittest import TestCase

import bytecodemanipulation.data_loader
from bytecodemanipulation.data.shared.instructions.LabelAssembly import LabelAssembly
from bytecodemanipulation.data.shared.instructions.PythonCodeAssembly import (
    PythonCodeAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.FunctionDefinitionAssembly import (
    FunctionDefinitionAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.IfAssembly import IFAssembly
from bytecodemanipulation.data.v3_10.instructions.JumpAssembly import JumpAssembly
from bytecodemanipulation.data.shared.instructions.LoadAssembly import LoadAssembly
from bytecodemanipulation.data.v3_10.instructions.LoadConstAssembly import (
    LoadConstAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.LoadFastAssembly import (
    LoadFastAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.LoadGlobalAssembly import (
    LoadGlobalAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.PopElementAssembly import (
    PopElementAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.ReturnAssembly import ReturnAssembly
from bytecodemanipulation.data.shared.instructions.StoreAssembly import StoreAssembly
from bytecodemanipulation.data.v3_10.instructions.store_fast_assembly import (
    StoreFastAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.store_global_assembly import (
    StoreGlobalAssembly,
)
from bytecodemanipulation.data.v3_10.instructions.while_assembly import WHILEAssembly
from bytecodemanipulation.data.v3_10.instructions.yield_assembly import YieldAssembly
from bytecodemanipulation.data.v3_10.instructions.OpAssembly import OpAssembly
from bytecodemanipulation.data.v3_10.instructions.CallAssembly import CallAssembly
from bytecodemanipulation.MutableFunction import MutableFunction

bytecodemanipulation.data_loader.INIT_ASSEMBLY = False
from bytecodemanipulation.assembler.Parser import *
from bytecodemanipulation.assembler.target import (
    assembly,
    label,
    jump as asm_jump,
    make_macro,
)
from bytecodemanipulation.assembler.Emitter import apply_inline_assemblies

try:
    from code_parser.parsers.common import IdentifierExpression
    from code_parser.lexers.common import IdentifierToken
except ImportError:
    from bytecodemanipulation.assembler.util.parser import IdentifierExpression
    from bytecodemanipulation.assembler.util.tokenizer import IdentifierToken

bytecodemanipulation.data_loader.load_assembly_instructions()

if typing.TYPE_CHECKING:
    pass

from tests.test_issues import compare_optimized_results
from bytecodemanipulation.Optimiser import cache_global_name, _OptimisationContainer


if bytecodemanipulation.data_loader.version == "3_10":
    pass
elif bytecodemanipulation.data_loader.version == "3_11":
    from bytecodemanipulation.data.v3_11.assembly_instructions import *
else:
    raise RuntimeError(
        f"Found not supported version: '{bytecodemanipulation.data_loader.version}'"
    )


GLOBAL = None


class TestParser(TestCase):
    def assertEqualList(
        self, correct: CompoundExpression, to_check: CompoundExpression
    ):
        if len(correct.children) != len(to_check.children):
            for check, corr in itertools.zip_longest(
                correct.children, to_check.children
            ):
                print(f"Expected {corr}, got {check}")

        self.assertEqual(
            len(correct.children), len(to_check.children), "Length of lists!"
        )

        for a, b in zip(correct.children, to_check.children):
            self.assertEqual(a, b)

    def test_syntax_error(self):
        def test():
            @apply_inline_assemblies
            def target():
                assembly(
                    """
LOAD 19 --> $test
    """
                )

        self.assertRaises(SyntaxError, test)

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
                        "test",
                        GlobalAccessExpression("test"),
                    ),
                    StoreGlobalAssembly(
                        "test",
                        LocalAccessExpression("test"),
                    ),
                    StoreGlobalAssembly("test", TopOfStackAccessExpression()),
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
            "STORE @test;\nSTORE $test;\nSTORE @global[10];\nSTORE $local[20]"
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
        expr = Parser(
            "YIELD\nYIELD @global\nYIELD *\nYIELD* $local\nYIELD -> %\nYIELD @global -> $local\n YIELD* -> @global\nYIELD* @global -> $local"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    YieldAssembly(),
                    YieldAssembly(GlobalAccessExpression("global")),
                    YieldAssembly(is_star=True),
                    YieldAssembly(LocalAccessExpression("local"), is_star=True),
                    YieldAssembly(target=TopOfStackAccessExpression()),
                    YieldAssembly(
                        GlobalAccessExpression("global"),
                        target=LocalAccessExpression("local"),
                    ),
                    YieldAssembly(
                        is_star=True, target=GlobalAccessExpression("global")
                    ),
                    YieldAssembly(
                        GlobalAccessExpression("global"),
                        True,
                        LocalAccessExpression("local"),
                    ),
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

IF @global 'test'
{
    JUMP test
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
                    IFAssembly(
                        GlobalAccessExpression("global"),
                        CompoundExpression([JumpAssembly("test")]),
                        "test",
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

WHILE $local 'test' {
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
                    WHILEAssembly(
                        LocalAccessExpression("local"),
                        CompoundExpression(
                            [StoreAssembly(GlobalAccessExpression("global"))]
                        ),
                        "test",
                    ),
                ]
            ),
            expr,
        )

    def test_jump(self):
        expr = Parser(
            "LABEL test\nJUMP test\nJUMP test IF @global\nJUMP test IF OP (@a == @b)\nJUMP test (@global)\nJUMP test (OP (@a == @b))\nJUMP test (@a == @b)"
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    LabelAssembly("test"),
                    JumpAssembly("test"),
                    JumpAssembly("test", GlobalAccessExpression("global")),
                    JumpAssembly(
                        "test",
                        OpAssembly(
                            OpAssembly.BinaryOperation(
                                GlobalAccessExpression("a"),
                                "==",
                                GlobalAccessExpression("b"),
                            )
                        ),
                    ),
                    JumpAssembly("test", GlobalAccessExpression("global")),
                    JumpAssembly(
                        "test",
                        OpAssembly(
                            OpAssembly.BinaryOperation(
                                GlobalAccessExpression("a"),
                                "==",
                                GlobalAccessExpression("b"),
                            )
                        ),
                    ),
                    JumpAssembly(
                        "test",
                        OpAssembly(
                            OpAssembly.BinaryOperation(
                                GlobalAccessExpression("a"),
                                "==",
                                GlobalAccessExpression("b"),
                            )
                        ),
                    ),
                ]
            ),
            expr,
        )

    def test_def_assembly(self):
        expr = Parser(
            """
DEF test () {}
DEF test <test> () {}
DEF test <!test> () {}
DEF test <test, test2> () {}
DEF test <test> (a) {}
DEF test <test> (a, b) {}
DEF test <test> (c=@d) {}
DEF test <test> () -> @target {}
"""
        ).parse()

        self.assertEqualList(
            CompoundExpression(
                [
                    FunctionDefinitionAssembly("test", [], [], CompoundExpression([])),
                    FunctionDefinitionAssembly(
                        "test", ["test"], [], CompoundExpression([])
                    ),
                    FunctionDefinitionAssembly(
                        "test", [("test", True)], [], CompoundExpression([])
                    ),
                    FunctionDefinitionAssembly(
                        "test", ["test", "test2"], [], CompoundExpression([])
                    ),
                    FunctionDefinitionAssembly(
                        "test",
                        ["test"],
                        [CallAssembly.Arg(IdentifierToken("a"))],
                        CompoundExpression([]),
                    ),
                    FunctionDefinitionAssembly(
                        "test",
                        ["test"],
                        [
                            CallAssembly.Arg(IdentifierToken("a")),
                            CallAssembly.Arg(IdentifierToken("b")),
                        ],
                        CompoundExpression([]),
                    ),
                    FunctionDefinitionAssembly(
                        "test",
                        ["test"],
                        [CallAssembly.KwArg("c", GlobalAccessExpression("d"))],
                        CompoundExpression([]),
                    ),
                    FunctionDefinitionAssembly(
                        "test",
                        ["test"],
                        [],
                        CompoundExpression([]),
                        GlobalAccessExpression("target"),
                    ),
                ]
            ),
            expr,
        )

    def test_python_assembly(self):
        expr = Parser(
            """
PYTHON {
    print("Hello World")
}
"""
        ).parse()

        self.assertEqualList(
            CompoundExpression([PythonCodeAssembly('print("Hello World")')]),
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

    def test_empty_with_comment(self):
        def target():
            assembly("# Hello World!")

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
            assembly(
                """
YIELD @GLOBAL
YIELD* @GLOBAL
YIELD* @GLOBAL -> $t
YIELD @GLOBAL -> $v"""
            )
            yield 0

        def compare():
            yield GLOBAL
            yield from GLOBAL
            t = yield from GLOBAL
            v = yield GLOBAL
            yield 0

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_call_assembly_partial(self):
        # Only here so below code works!
        _OptimisationContainer.get_for_target(functools).is_static = True

        def target(x):
            assembly(
                """
CALL PARTIAL @print ("Hello World!") -> $x
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        @cache_global_name("functools")
        def compare():
            x = functools.partial(print, "Hello World!")

        compare_optimized_results(self, target, compare, opt_ideal=2)

        _OptimisationContainer.get_for_target(functools).is_static = False

    def test_call_assembly(self):
        def target(x):
            assembly(
                """
CALL @print ("Hello World!") -> $x
# LOAD $error -> @global
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        target(self)

        def compare():
            x = print("Hello World!")

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_python_assembly(self):
        def target(x):
            assembly(
                """
PYTHON {
    print("Hello World!")
}
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        def compare():
            print("Hello World!")

        compare_optimized_results(self, target, compare)

    def test_module_importer_hook(self):
        import bytecodemanipulation.assembler.hook

        bytecodemanipulation.assembler.hook.hook()

        code = "import tests.test\nself.assertEqual(10, tests.test.test)"
        exec(code, {"self": self})

        bytecodemanipulation.assembler.hook.unhook()

    def test_walrus_assigment(self):
        def target():
            assembly(
                """
OP $local := 10
STORE $test
RETURN OP ($local + $test)
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        def compare():
            test = (local := 10)
            return local + test

        compare_optimized_results(self, target, compare, opt_ideal=0)

    def test_dynamic_attribute_access(self):
        def target(t):
            assembly(
                """
RETURN $t.("test_dynamic_attribute_access")
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(self), self.test_dynamic_attribute_access)

    def test_isinstance_check(self):
        def target():
            assembly(
                """
RETURN OP (10 isinstance @int)
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertTrue(target())

    def test_not_isinstance_check(self):
        def target():
            assembly(
                """
RETURN OP (10 isinstance @float)
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        # dis.dis(target)

        self.assertFalse(target())

    def test_issubclass_check(self):
        def target():
            assembly(
                """
RETURN OP (@int issubclass @object)
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertTrue(target())

    def test_not_issubclass_check(self):
        def target():
            assembly(
                """
RETURN OP (@int issubclass @float)
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        # dis.dis(target)

        self.assertFalse(target())

    def test_hasattr_check(self):
        def target(t):
            assembly(
                """
RETURN OP ($t hasattr "test_hasattr_check")
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertTrue(target(self))

    def test_not_hasattr_check(self):
        def target(t):
            assembly(
                """
RETURN OP ($t hasattr "no attr")
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        # dis.dis(target)

        self.assertFalse(target(self))

    def test_getattr_check(self):
        def target(t):
            assembly(
                """
RETURN OP ($t getattr "test_getattr_check")
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(self), self.test_getattr_check)


class TestMacro(TestCase):
    def test_basic(self):
        def target():
            assembly(
                """
    LOAD 1 -> $x
    MACRO test_basic {
        LOAD 0 -> $x
    }
    
    CALL MACRO test_basic()
    RETURN $x
    """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 0)

    def test_macro_local_access(self):
        def target():
            assembly(
                """
        MACRO test_macro_local_access {
            LOAD 1 -> $local
        }

        LOAD 0 -> $local
        CALL MACRO test_macro_local_access()
        RETURN $local
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 1)

    def test_macro_parameter_resolver(self):
        def target():
            assembly(
                """
        MACRO test_macro_parameter_resolver (!param) {
            LOAD &param -> $local
            LOAD 0 -> &param
        }

        LOAD 0 -> $local
        CALL MACRO test_macro_parameter_resolver(1)
        RETURN $local
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 1)

    def test_macro_parameter_duplicated_access_static(self):
        def target():
            assembly(
                """
        MACRO test_macro_parameter_duplicated_access_static (!param) {
            LOAD &param -> $local
            LOAD 2 -> &param
            LOAD &param -> $local
        }

        LOAD 0 -> $local
        CALL MACRO test_macro_parameter_duplicated_access_static(1)
        RETURN $local
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 2)

    def test_macro_parameter_static_invalid(self):
        def target():
            assembly(
                """
        MACRO test_macro_parameter_static_invalid (param) {
            LOAD 2 -> &param
        }

        CALL MACRO test_macro_parameter_static_invalid(1)
        RETURN $local
        """
            )
            return -1

        mutable = MutableFunction(target)
        self.assertRaises(SyntaxError, lambda: apply_inline_assemblies(mutable))

    def test_macro_local_name_override(self):
        def target():
            assembly(
                """
        MACRO test_macro_local_name_override (!param) {
            LOAD 10 -> $test
        }

        LOAD 0 -> $test
        CALL MACRO test_macro_local_name_override(1)
        RETURN $test
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 10)

    def test_macro_local_name_escape(self):
        def target():
            assembly(
                """
        MACRO test_macro_local_name_escape (!param) {
            LOAD 10 -> $MACRO_test
        }

        LOAD 0 -> $test
        CALL MACRO test_macro_local_name_escape(1)
        RETURN $test
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 0)

    def test_namespace_macro(self):
        def target():
            assembly(
                """
        NAMESPACE test_namespace {
            MACRO test_namespace_macro {
                RETURN 0
            }
        }

        CALL MACRO test_namespace:test_namespace_macro()
        RETURN 1
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 0)

    def test_namespace_macro_failure(self):
        def target():
            assembly(
                """
        NAMESPACE test_namespace {
            MACRO test_macro_failure {
                RETURN 0
            }
        }

        CALL MACRO test_macro_failure()
        RETURN 1
        """
            )
            return -1

        mutable = MutableFunction(target)
        self.assertRaises(NameError, lambda: apply_inline_assemblies(mutable))

    def test_namespace_macro_inner(self):
        def target():
            assembly(
                """
        NAMESPACE test_namespace {
            MACRO test_namespace_macro_inner {
                RETURN 0
            }
            
            CALL MACRO test_namespace_macro_inner()
            RETURN 1
        }
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 0)

    def test_namespace_macro_with_namespace(self):
        def target():
            assembly(
                """
        MACRO test_namespace:test_namespace_macro_with_namespace {
            RETURN 0
        }

        CALL MACRO test_namespace:test_namespace_macro_with_namespace()
        RETURN 1
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 0)

    def test_macro_paste(self):
        def target():
            assembly(
                """
        MACRO test_macro_paste (param) {
            MACRO_PASTE param
        }

        LOAD 0 -> $test
        CALL MACRO test_macro_paste({
            LOAD 10 -> $test
        })
        RETURN $test
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 10)

    def test_macro_paste_with_type_annotation(self):
        def target():
            assembly(
                """
        MACRO test_macro_paste_with_type_annotation (param CODE_BLOCK) {
            MACRO_PASTE param
        }

        LOAD 0 -> $test
        CALL MACRO test_macro_paste_with_type_annotation({
            LOAD 10 -> $test
        })
        RETURN $test
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 10)

    def test_macro_paste_with_type_annotation_failure(self):
        def target():
            assembly(
                """
        MACRO test_macro_paste_with_type_annotation_failure (param CODE_BLOCK) {
            MACRO_PASTE param
        }

        LOAD 0 -> $test
        CALL MACRO test_macro_paste_with_type_annotation_failure(10)
        RETURN $test
        """
            )
            return -1

        mutable = MutableFunction(target)
        self.assertRaises(NameError, lambda: apply_inline_assemblies(mutable))

    def test_macro_paste_use(self):
        def target():
            assembly(
                """
        MACRO test_macro_paste_use (param) {
            MACRO_PASTE param -> $test
        }

        LOAD 0 -> $test
        CALL MACRO test_macro_paste_use({
            LOAD 10
        })
        RETURN $test
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 10)

    def test_macro_overload(self):
        def target():
            assembly(
                """
        MACRO test_macro_overload 
        {
            RETURN 0
        }
        
        MACRO test_macro_overload(param)
        {
            RETURN 2
        }

        CALL MACRO test_macro_overload()
        RETURN 1
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 0)

    def test_macro_overload_2(self):
        def target():
            assembly(
                """
        MACRO test_macro_overload_2
        {
            RETURN 0
        }

        MACRO test_macro_overload_2(param)
        {
            RETURN 2
        }

        CALL MACRO test_macro_overload_2(10)
        RETURN 1
        """
            )
            return -1

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 2)

    def test_variable_macro_input(self):
        def target():
            assembly(
                """
        MACRO test_variable_macro_input (target VARIABLE) {
            LOAD 1 -> &target
        }

        LOAD 0 -> $local
        CALL MACRO test_variable_macro_input($local)
        RETURN $local
        """
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 1)

    def test_class_assembly(self):
        def target():
            test = None
            assembly(
                """
CLASS test{}"""
            )
            return test

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target().__name__, "test")

    def test_class_assembly_parent(self):
        def target():
            test = None
            assembly(
                """
CLASS test(~int){}"""
            )
            return test

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target().__bases__, (int,))

    def test_class_assembly_func_define(self):
        def target():
            test = None
            assembly(
                """
CLASS test
{
    DEF test()
    {
        RETURN 42
    }
}
"""
            )
            return test

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        cls = target()
        self.assertEqual(cls.test(), 42)

    def test_class_assembly_namespace_macro(self):
        def target():
            assembly(
                """
CLASS test
{
    MACRO test_macro()
    {
        RETURN 1
    }
}

CALL MACRO test:test_macro()
"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 1)

    def test_transform_to_macro(self):
        @make_macro("TestMacro:test_transform_to_macro")
        def test_transform_to_macro():
            test = 1

        def target():
            test = -1
            assembly(
                """
LOAD 0 -> $test
CALL MACRO TestMacro:test_transform_to_macro()
"""
            )
            return test

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 1)

    def test_transform_to_macro_2(self):
        @make_macro("TestMacro:test_transform_to_macro_2")
        def test_transform_to_macro(a):
            test = a

        def target():
            test = -1
            assembly(
                """
LOAD 0 -> $test
CALL MACRO TestMacro:test_transform_to_macro_2(1)
"""
            )
            return test

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 1)

    def test_transform_to_macro_3(self):
        @make_macro("TestMacro:test_transform_to_macro_3")
        def test_transform_to_macro(a):
            test = a + a

        def target():
            test = -1
            value = [1, 2]
            assembly(
                """
LOAD 0 -> $test
CALL MACRO TestMacro:test_transform_to_macro_3({ CALL $value.pop() })
"""
            )
            return test

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), 3)

    def test_transform_to_macro_or_else_error(self):
        @make_macro(
            "TestMacro:test_transform_to_macro_or_else_error", prevent_direct_calls=True
        )
        def test_transform_to_macro():
            pass

        self.assertRaises(RuntimeError, test_transform_to_macro)

    def test_macro_capture_arg_in_inner_func(self):
        def target():
            tar = lambda: 0
            assembly(
                """
MACRO test_macro_capture_arg_in_inner_func(a)
{
    DEF tar()
    {
        RETURN &a
    }
}

CALL MACRO test_macro_capture_arg_in_inner_func(2)
"""
            )
            return tar

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        # dis.dis(target)

        self.assertEqual(target()(), 2)

    def test_macro_capture_arg_in_inner_func_2(self):
        def target():
            tar = lambda: 0
            assembly(
                """
MACRO test_macro_capture_arg_in_inner_func_2(a CODE_BLOCK)
{
    DEF tar()
    {
        MACRO_PASTE a
    }
}

CALL MACRO test_macro_capture_arg_in_inner_func_2({ RETURN 2 })
"""
            )
            return tar

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        # dis.dis(target)

        self.assertEqual(target()(), 2)

    def test_for_loop_basic(self):
        def target():
            iterable = [0, 1, 2, 3]
            result = []
            assembly(
                """
FOREACH $p IN $iterable
{
    CALL $result.append(OP ($p + 1)) -> \\
}
"""
            )
            return result

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), [1, 2, 3, 4])

    def test_for_loop_double(self):
        def target():
            iterable = [0, 1, 2, 3]
            iterable_2 = [1, 2, 3, 4]
            result = []
            assembly(
                """
FOREACH $p, $q IN $iterable, $iterable_2
{
    CALL $result.append(OP ($p + $q)) -> \\
}
"""
            )
            return result

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), [1, 3, 5, 7])

    def test_for_loop_product(self):
        def target():
            iterable = [0, 1]
            iterable_2 = [1, 2]
            result = []
            assembly(
                """
FOREACH $p IN $iterable * $iterable_2
{
    CALL $result.append(OP ($p[0] * $p[1])) -> \\
}
"""
            )
            return result

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), [0, 0, 1, 2])
