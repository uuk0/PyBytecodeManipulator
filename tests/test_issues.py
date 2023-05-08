import math
import typing
import unittest

from bytecodemanipulation import Emulator

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Optimiser import apply_now
from bytecodemanipulation.Optimiser import cache_global_name
from tests.util import compare_optimized_results


class TestIssue2(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target():
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
            print(typing.cast(int, 2), 0)


class TestIssue4(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target():
            x = 0
            y = 0
            z = None
            print(x, typing.cast, typing.cast(y, z.p))


class TestIssue5(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target():
            try:
                pass
            except:
                pass

    def test_2(self):
        @apply_now()
        def target():
            try:
                pass
            except TypeError:
                pass

    def test_3(self):
        @apply_now()
        async def target():
            try:
                pass
            except TypeError:
                raise

    # def test_4(self):
    #     @apply_now()
    #     async def target():
    #         try:
    #             pass
    #         except TypeError:
    #             raise
    #         except ValueError:
    #             pass


class TestIssueTODO(unittest.TestCase):
    def setUp(self) -> None:
        self.old = MutableFunction(MutableFunction.assemble_instructions_from_tree)

    def tearDown(self) -> None:
        instance = MutableFunction(MutableFunction.assemble_instructions_from_tree)
        instance.copy_from(self.old)
        instance.reassign_to_function()

    # def test_1(self):
    #     apply_now()(MutableFunction.assemble_instructions_from_tree)
    #
    #     dis.dis(Instruction.trace_stack_position)
    #
    #     def target(t):
    #         x(typing.cast(int, 2), 0)
    #
    #     Emulator.run_code(apply_now(), target)


class TestIssue6(unittest.TestCase):
    def test_1(self):
        @apply_now()
        @cache_global_name("math", lambda: math)
        def rotate_point(a, b):
            return math.cos(a) - math.sin(b)

        # dis.dis(rotate_point)

        self.assertEqual(
            Emulator.run_code(rotate_point, 1, 2), math.cos(1) - math.sin(2)
        )
        self.assertEqual(rotate_point(1, 2), math.cos(1) - math.sin(2))
