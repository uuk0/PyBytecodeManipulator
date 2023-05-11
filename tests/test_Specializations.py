import dis
from unittest import TestCase

import typing

from bytecodemanipulation.MutableFunction import MutableFunction

from bytecodemanipulation.Optimiser import _OptimisationContainer
from tests.util import compare_optimized_results
from tests.util import BUILTIN_INLINE


def optimise(target: typing.Callable):
    mutable = MutableFunction(target)
    BUILTIN_INLINE._inline_load_globals(mutable)
    mutable.reassign_to_function()
    _OptimisationContainer.get_for_target(target).run_optimisers()


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
