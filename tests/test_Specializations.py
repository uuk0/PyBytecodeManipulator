from unittest import TestCase

import typing

from bytecodemanipulation.MutableFunction import MutableFunction

from bytecodemanipulation.Optimiser import _OptimisationContainer
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
