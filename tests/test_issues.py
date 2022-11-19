import dis
import unittest

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Optimiser import _OptimisationContainer
from bytecodemanipulation.Optimiser import apply_now
from bytecodemanipulation.Optimiser import BUILTIN_CACHE

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

    """
    Currently testing:
    
    def test(self):
        @apply_now()
        def target(t):
            if t.__instructions is not None:
                t.__instructions.clear()
            else:
                t.__instructions = []

            extra: int = 0
            for i in range(0, len(t.__raw_code), 2):
                opcode, arg = t.__raw_code[i: i + 2]

                if opcode == Opcodes.EXTENDED_ARG:
                    extra = extra * 256 + arg
                    t.__instructions.append(
                        Instruction(t, i // 2, "NOP", _decode_next=False)
                    )

                else:
                    arg += extra * 256
                    extra = 0

                    if opcode == Opcodes.FOR_ITER:
                        arg += 1

                    t.__instructions.append(
                        Instruction(t, i // 2, opcode, arg=arg, _decode_next=False)
                    )

            for i, instruction in enumerate(t.instructions):
                instruction.update_owner(t, i)

            t.prepare_previous_instructions()"""

