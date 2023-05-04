import dis
from unittest import TestCase

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.MutableFunctionHelpers import *

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

        # dis.dis(main)

        main()
        self.assertTrue(INVOKED)
