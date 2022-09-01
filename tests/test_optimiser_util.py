import dis
from unittest import TestCase
from bytecodemanipulation.optimiser_util import *
from bytecodemanipulation.Optimiser import guarantee_constant_result, cache_global_name, _OptimisationContainer, BUILTIN_CACHE


BUILTIN_INLINE = _OptimisationContainer(None)
BUILTIN_INLINE.dereference_global_name_cache.update(BUILTIN_CACHE)


@guarantee_constant_result()
def test_target(a, b):
    return a + b


class TestOptimiserUtil(TestCase):
    def test_inline_constant_method_invoke(self):
        def target():
            return max(1, 2)

        mutable = MutableFunction(target)
        BUILTIN_INLINE._inline_load_globals(mutable)
        inline_constant_method_invokes(mutable)
        remove_nops(mutable)

        mutable.assemble_instructions()
        mutable.reassign_to_function()

        self.assertEqual(2, mutable.instructions[0].arg_value)

    def test_inline_binary_op(self):
        def target():
            return 1 + 1

        mutable = MutableFunction(target)
        BUILTIN_INLINE._inline_load_globals(mutable)
        inline_constant_method_invokes(mutable)
        remove_nops(mutable)

        mutable.assemble_instructions()
        mutable.reassign_to_function()

        self.assertEqual(2, mutable.instructions[0].arg_value)

    def test_inline_const_function(self):
        @cache_global_name("test_target", lambda: test_target)
        def target():
            return test_target(1, 1)

        _OptimisationContainer.get_for_target(target).run_optimisers()

        mutable = MutableFunction(target)

        self.assertEqual(2, mutable.instructions[0].arg_value)

