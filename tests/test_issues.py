import dis
import types
import typing
import unittest

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Optimiser import _OptimisationContainer
from bytecodemanipulation.Optimiser import apply_now
from bytecodemanipulation.Optimiser import BUILTIN_CACHE
from bytecodemanipulation.Optimiser import guarantee_builtin_names_are_protected
from bytecodemanipulation.Optimiser import guarantee_module_import

BUILTIN_INLINE = _OptimisationContainer(None)
BUILTIN_INLINE.dereference_global_name_cache.update(BUILTIN_CACHE)


def compare_optimized_results(case: unittest.TestCase, target, ideal, opt_ideal=1, msg=...):
    mutable = MutableFunction(target)
    BUILTIN_INLINE._inline_load_globals(mutable)
    mutable.reassign_to_function()

    _OptimisationContainer.get_for_target(target).run_optimisers()

    if opt_ideal > 0:
        mutable = MutableFunction(ideal)
        BUILTIN_INLINE._inline_load_globals(mutable)
        mutable.reassign_to_function()

    if opt_ideal > 1:
        _OptimisationContainer.get_for_target(ideal).run_optimisers()

    mutable = MutableFunction(target)
    mutable2 = MutableFunction(ideal)

    eq = len(mutable.instructions) == len(mutable2.instructions)

    if eq:
        eq = all(
            a.lossy_eq(b)
            for a, b in zip(mutable.instructions, mutable2.instructions)
        )

    if not eq:
        mutable.dump_info("./tests/target.json")
        mutable.dump_info("./tests/ideal.json")

        print("target")
        dis.dis(target)
        print("compare")
        dis.dis(ideal)

    case.assertEqual(len(mutable.instructions), len(mutable2.instructions), msg=(msg if msg is not ... else "...") + ": Instruction count !=")

    for a, b in zip(mutable.instructions, mutable2.instructions):
        case.assertTrue(a.lossy_eq(b), msg=f"{msg if msg is not ... else '...'}: Instruction {a} != {b}")


class TestIssue2(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target(t):
            for x in (0, 1):
                pass

    def test_2(self):
        """
        1 LOAD_CONST 0
        2 STORE_FAST extra
        3 LOAD_CONST (0, 1)
        4 GET_ITER
        5 FOR_ITER 8
        6 STORE_FAST i -> POP_TOP
        7 JUMP_ABSOLUTE 5
        8 LOAD_CONST None
        9 RETURN_VALUE
        """
        @apply_now()
        def target(t):
            extra: int = 0
            for i in (0, 1):
                pass

        def compare(t):
            for i in (0, 1):
                pass

        compare_optimized_results(self, target, compare, opt_ideal=2)


class TestIssue3(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target(t):
            x(typing.cast(int, 2), 0)


class TestIssue4(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target():
            c(x, typing.cast, typing.cast(y, z.p))


class TestIssue5(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target():
            try:
                pass
            except:
                pass


class TestIssue6(unittest.TestCase):
    def setUp(self) -> None:
        self.old = MutableFunction(MutableFunction.assemble_instructions_from_tree)

    def tearDown(self) -> None:
        instance = MutableFunction(MutableFunction.assemble_instructions_from_tree)
        instance.copy_from(self.old)
        instance.reassign_to_function()

    def test_1(self):
        apply_now()(MutableFunction.assemble_instructions_from_tree)

        dis.dis(MutableFunction.assemble_instructions_from_tree)

        # @apply_now()
        # def target(t):
        #     x(typing.cast(int, 2), 0)

    """
    Currently testing:
    
    def test(self):
        @apply_now()
        def target(t):
            pass"""

