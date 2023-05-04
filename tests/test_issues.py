import dis
import math
import os
import random
import traceback
import types
import typing
import unittest

import asyncio

from bytecodemanipulation import Emulator

from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Opcodes import Opcodes
from bytecodemanipulation.Optimiser import _OptimisationContainer
from bytecodemanipulation.Optimiser import apply_now
from bytecodemanipulation.Optimiser import BUILTIN_CACHE
from bytecodemanipulation.Optimiser import cache_global_name
from bytecodemanipulation.Optimiser import guarantee_builtin_names_are_protected

BUILTIN_INLINE = _OptimisationContainer(None)
BUILTIN_INLINE.dereference_global_name_cache.update(BUILTIN_CACHE)


def compare_optimized_results(
    case: unittest.TestCase, target, ideal, opt_ideal=1, msg=...
):
    if hasattr(target, "_debug_wrapper"):
        mutable = target._debug_wrapper
        mutable.reassign_to_function()
    else:
        mutable = MutableFunction(target)

    BUILTIN_INLINE._inline_load_globals(mutable)

    if not hasattr(target, "_debug_wrapper"):
        mutable.reassign_to_function()

    _OptimisationContainer.get_for_target(mutable.target).run_optimisers()

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
            a.lossy_eq(b) for a, b in zip(mutable.instructions, mutable2.instructions)
        )

    if not eq:
        local = os.path.dirname(__file__)
        mutable.dump_info(local + "/target.json")
        mutable.dump_info(local + "/ideal.json")

        print("target")
        if hasattr(target, "_debug_wrapper"):
            for instr in target._debug_wrapper.instructions:
                print(instr)
        else:
            dis.dis(target)

        print("compare")
        dis.dis(ideal)

    case.assertEqual(
        len(mutable.instructions),
        len(mutable2.instructions),
        msg=(msg if msg is not ... else "...") + ": Instruction count !=",
    )

    for a, b in zip(mutable.instructions, mutable2.instructions):
        if isinstance(a.arg_value, Exception):
            case.assertTrue(
                isinstance(b.arg_value, Exception)
                and a.arg_value.args == b.arg_value.args,
                msg=f"{msg if msg is not ... else '...'}: Instruction {a} != {b}",
            )
        else:
            case.assertTrue(
                a.lossy_eq(b),
                msg=f"{msg if msg is not ... else '...'}: Instruction {a} != {b}",
            )


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
