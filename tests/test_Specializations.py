import dis
import random
from unittest import TestCase

import typing

from bytecodemanipulation.MutableFunction import MutableFunction

from bytecodemanipulation.Optimiser import _OptimisationContainer, cache_global_name
from bytecodemanipulation.assembler.target import assembly, apply_operations
from tests.util import compare_optimized_results
from tests.util import BUILTIN_INLINE


def optimise(target: typing.Callable):
    mutable = MutableFunction(target)
    BUILTIN_INLINE._inline_load_globals(mutable)
    mutable.reassign_to_function()
    _OptimisationContainer.get_for_target(target).run_optimisers()


x = None

class TestSpecializations(TestCase):
    def tearDown(self) -> None:
        from bytecodemanipulation.data.shared import builtin_spec

        builtin_spec.ASSERT_TYPE_CASTS = False

    def test_typing_cast_error(self):
        from bytecodemanipulation.data.shared import builtin_spec

        builtin_spec.ASSERT_TYPE_CASTS = True

        def target():
            return typing.cast(int, [])

        optimise(target)

        self.assertRaises(ValueError, target)

        try:
            target()
        except ValueError as e:
            self.assertEqual(
                ("expected data type '<class 'int'>', but got '<class 'list'>'",),
                e.args,
            )

        builtin_spec.ASSERT_TYPE_CASTS = False

    def test_sum_operator(self):
        def target():
            return sum((1, 2, 3))

        def compare():
            return 6

        compare_optimized_results(self, target, compare)

    def test_specialization_all(self):
        def target(a):
            return all((a, True, True))

        def compare(a):
            return a

        compare_optimized_results(self, target, compare)

    def test_specialization_all_false(self):
        def target(a):
            return all((a, True, False))

        def compare(a):
            return False

        compare_optimized_results(self, target, compare)

    def test_specialization_any(self):
        def target(a):
            return any((a, False, False))

        def compare(a):
            return a

        compare_optimized_results(self, target, compare)

    def test_specialization_any_false(self):
        def target(a):
            return any((a, True, False))

        def compare(a):
            return True

        compare_optimized_results(self, target, compare)

    def test_empty_tuple(self):
        def target():
            assembly("RETURN OP (tuple ())")

        apply_operations(target)

        compare_optimized_results(self, target, lambda: tuple(), opt_ideal=2)

    def test_third_arg_not_0(self):
        def target():
            range(1, 2, 0)

        @cache_global_name("x", lambda: ValueError('range() arg 3 must not be zero'))
        def compare():
            raise x

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_random_Random_randrange_empty_error(self):
        @cache_global_name("x", lambda: random.Random.randrange)
        def target():
            x()

        @cache_global_name("x", lambda: ValueError("Random.randrange() missing 1 required positional argument: 'start'"))
        def compare():
            raise x

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_range_more_args(self):
        def target():
            range(1, 2, 3, 4)

        @cache_global_name("x", lambda: TypeError('range expected at most 3 arguments, got 4'))
        def compare():
            raise x

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_random_randrange_more_args(self):
        @cache_global_name("x", lambda: random.randrange)
        def target():
            x(1, 2, 3, 4)

        @cache_global_name("x", lambda: TypeError('Random.randrange() takes from 2 to 4 positional arguments but 4 were given'))
        def compare():
            raise x

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_Random_random_randrange_more_args(self):
        @cache_global_name("x", lambda: random.Random.randrange)
        def target():
            x(1, 2, 3, 4)

        @cache_global_name("x", lambda: TypeError('Random.randrange() takes from 2 to 4 positional arguments but 4 were given'))
        def compare():
            raise x

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_small_range_without_const_arg_1_0(self):
        def target(x):
            return range(x)

        def compare(x):
            return range(x)

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_small_range_without_const_arg_2_1(self):
        def target(x):
            return range(x, 0)

        def compare(x):
            return range(x, 0)

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_small_range_without_const_arg_2_2(self):
        def target(x):
            return range(0, x)

        def compare(x):
            return range(0, x)

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_small_range_without_const_arg_3(self):
        def target(x):
            return range(0, 1, x)

        def compare(x):
            return range(0, 1, x)

        compare_optimized_results(self, target, compare, opt_ideal=2)

