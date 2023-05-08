import math
import random
from unittest import TestCase

from bytecodemanipulation.optimiser_util import *
from bytecodemanipulation.Optimiser import (
    guarantee_constant_result,
    cache_global_name,
    _OptimisationContainer,
)
from tests.util import compare_optimized_results
from tests.util import JsonTestEntry


@guarantee_constant_result()
def test_target(a, b):
    return a + b


@cache_global_name("test_target", lambda: test_target)
class Outer_test_inline_const_function_on_parent:
    @staticmethod
    def target():
        return test_target(1, 1)


class TestOptimiserUtil(TestCase):
    def test_builtins(self):
        test = JsonTestEntry.from_file("data/test_builtins.json")
        test.run_tests(self)

    def test_typing(self):
        test = JsonTestEntry.from_file("data/test_typing.json")
        test.run_tests(self)

    def test_range_arg_count_issue(self):
        def target():
            range()

        def compare():
            raise TypeError("range expected at least 1 argument, got 0")

        try:
            target()
        except TypeError as e:
            self.assertEqual("range expected at least 1 argument, got 0", e.args[0])
        else:
            self.assertTrue(False, "should not be reached!")

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_random_randrange_arg_count_issue(self):
        @cache_global_name("random")
        def target():
            random.randrange()

        def compare():
            raise TypeError(
                "Random.randrange() missing 1 required positional argument: 'start'"
            )

        try:
            target()
        except TypeError as e:
            self.assertEqual(
                "Random.randrange() missing 1 required positional argument: 'start'",
                e.args[0],
            )
        else:
            self.assertTrue(False, "should not be reached!")

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_range_arg_type_issue(self):
        def target():
            range(1.5)

        def compare():
            raise TypeError("'float' object cannot be interpreted as an integer")

        try:
            target()
        except TypeError as e:
            self.assertEqual(
                "'float' object cannot be interpreted as an integer", e.args[0]
            )
        else:
            self.assertTrue(False, "should not be reached!")

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_range_arg_type_issue_2(self):
        def target():
            range("")

        def compare():
            raise TypeError("'str' object cannot be interpreted as an integer")

        try:
            target()
        except TypeError as e:
            self.assertEqual(
                "'str' object cannot be interpreted as an integer", e.args[0]
            )
        else:
            self.assertTrue(False, "should not be reached!")

        compare_optimized_results(self, target, compare, opt_ideal=2)

    def test_inline_binary_op(self):
        compare_optimized_results(self, lambda: 1 + 1, lambda: 2)

    def test_inline_const_function(self):
        @cache_global_name("test_target", lambda: test_target)
        def target():
            return test_target(1, 1)

        compare_optimized_results(self, target, lambda: 2)

    def test_inline_math_attr(self):
        @cache_global_name("math", lambda: math)
        def target():
            return math.sin(2)

        compare_optimized_results(self, target, eval(f"lambda: {math.sin(2)}"))

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

        compare_optimized_results(self, target, lambda: 1)

    def test_branch_remover_2(self):
        def target():
            if 0 != 0:
                return 0
            return 1

        compare_optimized_results(self, target, lambda: 1)

    def test_load_pop_pair_removal(self):
        def target():
            a = 10

        compare_optimized_results(self, target, lambda: None)

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

        # dis.dis(target)

        self.assertEqual(mutable.instructions[0].arg_value, None)

    def test_empty_range_from_invalid_range(self):
        @cache_global_name("range", lambda: range)
        def target():
            return range(2, 0)

        compare_optimized_results(self, target, lambda: tuple(), opt_ideal=2)

        @cache_global_name("range", lambda: range)
        def target():
            return range(2, 0, 1)

        compare_optimized_results(self, target, lambda: tuple(), opt_ideal=2)

        @cache_global_name("range", lambda: range)
        def target():
            return range(0, 2, -1)

        compare_optimized_results(self, target, lambda: tuple(), opt_ideal=2)

    def test_sum_specializations(self):
        @cache_global_name("sum", lambda: sum)
        def target(a):
            return sum((a,))

        compare_optimized_results(self, target, lambda a: a)

        @cache_global_name("sum", lambda: sum)
        def target(a, b):
            return sum((a, b))

        compare_optimized_results(self, target, lambda a, b: a + b)

        # we currently cannot test 3 or more args, as that would require reordering of instructions
