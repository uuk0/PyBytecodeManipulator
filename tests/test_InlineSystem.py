import dis
from unittest import TestCase

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.MutableFunctionHelpers import *
from bytecodemanipulation.Optimiser import inline_calls, apply_now, cache_global_name
from tests.util import compare_optimized_results

INVOKED = False


class TestMethodInsert(TestCase):
    def test_simple(self):
        def main():
            pass

        def insert():
            global INVOKED
            INVOKED = True

        global INVOKED
        INVOKED = False
        insert()
        self.assertTrue(INVOKED)
        INVOKED = False

        main_mut = MutableFunction(main)
        insert_mut = MutableFunction(insert)

        insert_method_into(main_mut, main_mut.instructions[0], insert_mut)
        main_mut.reassign_to_function()

        main()
        self.assertTrue(INVOKED)

    def test_inline_call_simple(self):
        global call

        @inline_calls
        def call():
            return 1

        @cache_global_name("call", lambda: call)
        def target():
            return call()

        apply_now()(target)

        compare_optimized_results(self, target, call)
        self.assertEqual(target(), 1)

    def test_inline_call_protect_local(self):
        global call

        @inline_calls
        def call():
            x = 2

        @cache_global_name("call", lambda: call)
        def target():
            x = 1
            call()
            return x

        apply_now()(target)

        self.assertEqual(target(), 1)

    def test_apply_duplicate_call(self):
        global call
        global counter
        counter = 0

        @inline_calls
        def call():
            global counter
            counter += 1

        @cache_global_name("call", lambda: call)
        def target():
            call()
            call()

        apply_now()(target)

        call = None

        target()
        self.assertEqual(counter, 2)
