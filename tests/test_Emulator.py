from unittest import TestCase
from bytecodemanipulation.Emulator import run_code
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.opcodes.Opcodes import Opcodes


class TestEmulator(TestCase):
    def test_run_code_simple(self):
        self.assertEqual(run_code(lambda: 10), 10)
        self.assertEqual(run_code(lambda x: x, 10), 10)

    def test_invalid_arg_count(self):
        self.assertRaises(ValueError, lambda: run_code(lambda x: x))

    def test_pop_top(self):
        code = [
            Instruction(Opcodes.LOAD_CONST, 10),
            Instruction(Opcodes.LOAD_CONST, abs),
            Instruction(Opcodes.LOAD_CONST, 5),
            Instruction(Opcodes.CALL_FUNCTION, arg=1),
            Instruction(Opcodes.POP_TOP),
            Instruction(Opcodes.RETURN_VALUE),
        ]

        mutable = MutableFunction.create_empty()
        mutable.assemble_fast_unchained(code)

        self.assertEqual(run_code(mutable), 10)

    def test_dup_top(self):
        code = [
            Instruction(Opcodes.LOAD_CONST, 10),
            Instruction(Opcodes.DUP_TOP),
            Instruction(Opcodes.LOAD_CONST, abs),
            Instruction(Opcodes.ROT_TWO),
            Instruction(Opcodes.CALL_FUNCTION, arg=1),
            Instruction(Opcodes.POP_TOP),
            Instruction(Opcodes.RETURN_VALUE),
        ]

        mutable = MutableFunction.create_empty()
        mutable.assemble_fast_unchained(code)

        self.assertEqual(run_code(mutable), 10)

    def test_for_loop(self):
        def target():
            x = 0
            # sourcery skip: no-loop-in-tests
            for i in range(10):
                x += i
            return x

        self.assertEqual(run_code(target), 45)

    def test_func_call_call(self):
        global a

        def a():
            return 10

        def b():
            return a()

        self.assertEqual(run_code(b), 10)

    def test_func_func_generator(self):
        global a

        def a():
            yield 10

        def b():
            return next(a())

        self.assertEqual(run_code(b), 10)

    def test_func_func_generator_yield_from(self):
        global a

        def a():
            yield from [10, 5]

        def b():
            return next(a())

        self.assertEqual(run_code(b), 10)

    def test_func_func_exc(self):
        global a

        def a():
            raise ValueError

        def b():
            return a()

        self.assertRaises(ValueError, lambda: run_code(b))

    def test_func_func_exc_2(self):
        global a

        def a():
            raise ValueError

        a._no_emulation = True

        def b():
            return a()

        self.assertRaises(ValueError, lambda: run_code(b))
