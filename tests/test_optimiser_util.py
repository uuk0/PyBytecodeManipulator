import dis
import math
from unittest import TestCase
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.optimiser_util import *
from bytecodemanipulation.Optimiser import (
    guarantee_constant_result,
    cache_global_name,
    _OptimisationContainer,
    BUILTIN_CACHE,
)


BUILTIN_INLINE = _OptimisationContainer(None)
BUILTIN_INLINE.dereference_global_name_cache.update(BUILTIN_CACHE)


@guarantee_constant_result()
def test_target(a, b):
    return a + b


@cache_global_name("test_target", lambda: test_target)
class Outer_test_inline_const_function_on_parent:
    @staticmethod
    def target():
        return test_target(1, 1)


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

    def test_inline_math_attr(self):
        @cache_global_name("math", lambda: math)
        def target():
            return math.sin(2)

        _OptimisationContainer.get_for_target(target).run_optimisers()

        mutable = MutableFunction(target)

        self.assertEqual(math.sin(2), mutable.instructions[0].arg_value)

    def test_inline_const_function_on_parent(self):
        container = _OptimisationContainer.get_for_target(
            Outer_test_inline_const_function_on_parent
        )
        container.run_optimisers()

        mutable = MutableFunction(Outer_test_inline_const_function_on_parent.target)

        self.assertEqual(2, mutable.instructions[0].arg_value)

    def test_branch_remover(self):
        def target():
            if False:
                return 0
            return 1

        mutable = MutableFunction(target)
        remove_branch_on_constant(mutable)
        mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())
        mutable.reassign_to_function()

        self.assertEqual(mutable.instructions[0].arg_value, 1)

    def test_branch_remover_2(self):
        def target():
            if 0 != 0:
                return 0
            return 1

        dis.dis(target)

        mutable = MutableFunction(target)
        inline_constant_binary_ops(mutable)
        remove_branch_on_constant(mutable)
        mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())
        mutable.reassign_to_function()

        dis.dis(target)

        self.assertEqual(mutable.instructions[0].arg_value, 1)

    def test_load_pop_pair_removal(self):
        def target():
            a = 10

        mutable = MutableFunction(target)
        remove_local_var_assign_without_use(mutable)
        inline_const_value_pop_pairs(mutable)
        mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())
        mutable.reassign_to_function()

        self.assertEqual(mutable.instructions[0].arg_value, None)

    def test_remove_list_build(self):
        def target():
            [200, 400, 200]
            a = [10]

        mutable = MutableFunction(target)
        remove_local_var_assign_without_use(mutable)
        inline_const_value_pop_pairs(mutable)
        inline_const_value_pop_pairs(mutable)
        mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())
        mutable.reassign_to_function()

        self.assertEqual(mutable.instructions[0].arg_value, None)

    # TODO: is there a way to make this work?
    # def test_remove_list_build_stacked(self):
    #     def target():
    #         [200, 400, 200, [342, 234]]
    #
    #     dis.dis(target)
    #
    #     mutable = MutableFunction(target)
    #     remove_local_var_assign_without_use(mutable)
    #     inline_const_value_pop_pairs(mutable)
    #     inline_const_value_pop_pairs(mutable)
    #     mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())
    #     mutable.reassign_to_function()
    #
    #     dis.dis(target)
    #
    #     self.assertEqual(mutable.instructions[0].arg_value, None)

    def test_remove_list_build_stacked_2(self):
        def target():
            [200, 400, 200, (342, 234)]

        mutable = MutableFunction(target)
        remove_local_var_assign_without_use(mutable)
        inline_const_value_pop_pairs(mutable)
        inline_const_value_pop_pairs(mutable)
        mutable.assemble_instructions_from_tree(mutable.instructions[0].optimise_tree())
        mutable.reassign_to_function()

        dis.dis(target)

        self.assertEqual(mutable.instructions[0].arg_value, None)

    def test_inline_static_attribute_access_typing(self):
        def target():
            return typing.cast(int, 0)

        _OptimisationContainer.get_for_target(target).run_optimisers()

        dis.dis(target)

        mutable = MutableFunction(target)
        self.assertEqual(
            Instruction.create(Opcodes.LOAD_CONST, 0), mutable.instructions[0]
        )

    def compare_optimized_results(self, target, ideal, opt_ideal=1):
        mutable = MutableFunction(target)
        BUILTIN_INLINE._inline_load_globals(mutable)
        mutable.reassign_to_function()

        _OptimisationContainer.get_for_target(target).run_optimisers()

        print("target")
        dis.dis(target)

        if opt_ideal > 0:
            mutable = MutableFunction(ideal)
            BUILTIN_INLINE._inline_load_globals(mutable)
            mutable.reassign_to_function()

        if opt_ideal > 1:
            _OptimisationContainer.get_for_target(ideal).run_optimisers()

        print("compare")
        dis.dis(ideal)

        mutable = MutableFunction(target)
        mutable2 = MutableFunction(ideal)
        self.assertEqual(mutable.instructions, mutable2.instructions)

    def test_spec_compress_min_max_call(self):
        self.compare_optimized_results(lambda x: min(x, 1, 2), lambda x: min(x, 1))
        self.compare_optimized_results(lambda x: max(x, 1, 2), lambda x: max(x, 2))

    def test_spec_small_range(self):
        self.compare_optimized_results(lambda: range(1, 5, 1), lambda: range(1, 5))
        self.compare_optimized_results(lambda: range(0, 3), lambda: range(3))

        self.compare_optimized_results(lambda: range(0, 0), lambda: tuple(), opt_ideal=2)
        self.compare_optimized_results(lambda: range(0, 1), lambda: (0,))
        self.compare_optimized_results(lambda: range(0, 2), lambda: (0, 1))

    def test_spec_all(self):
        self.compare_optimized_results(lambda x: all((x, False)), lambda x: False)
        self.compare_optimized_results(lambda x: all((x, 0)), lambda x: False)
        self.compare_optimized_results(lambda x: all((x, 0, True)), lambda x: False)

        self.compare_optimized_results(lambda x: all((x, True)), lambda x: all((x,)))
        self.compare_optimized_results(lambda x: all((x, True, 1)), lambda x: all((x,)))

    def test_spec_any(self):
        self.compare_optimized_results(lambda x: any((x, True)), lambda x: True)
        self.compare_optimized_results(lambda x: any((x, False)), lambda x: any((x,)))
        self.compare_optimized_results(lambda x: any((x, False, True, 0)), lambda x: True)
