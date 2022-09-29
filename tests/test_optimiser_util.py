import dis
import math
from unittest import TestCase
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
        self.assertEqual(Instruction.create(Opcodes.LOAD_CONST, 0), mutable.instructions[0])
