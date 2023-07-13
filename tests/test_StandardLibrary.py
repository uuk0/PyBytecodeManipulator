import os.path
import time
from unittest import TestCase
import dis

from bytecodemanipulation.Emulator import run_code
from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.assembler.target import *
from bytecodemanipulation.assembler.Emitter import apply_inline_assemblies


class StandardLibraryTest(TestCase):
    def setUp(self):
        import bytecodemanipulation.assembler.hook as hook

        hook.hook()

        def target():
            assembly("""
MACRO_IMPORT bytecodemanipulation.standard_library""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        target()

    # todo: can we test somehow the input system

    def test_type_check_raise(self):
        def target():
            assembly("""std:check_type(~int, "test", "exception")""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertRaises(ValueError, target)

    def test_type_check_raise_with_default_text(self):
        def target():
            assembly("""std:check_type(@int, "test")""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertRaises(ValueError, target)

    def test_file_list(self):
        file_name = os.path.dirname(__file__).replace("\\", "\\\\")
        code = f'''def target():
            assembly("""
MACRO_IMPORT bytecodemanipulation.standard_library

std:os:file_walker("{file_name}", $file, {{
    YIELD $file
}})
""")
            yield 0'''

        space = globals().copy()
        exec(code, space)
        target = space["target"]

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        files = list(target())[:-1]
        self.assertEqual(
            set(files),
            set(
                filter(
                    lambda e: os.path.isfile(e), os.listdir(os.path.dirname(__file__))
                )
            ),
        )

    def test_stream_simple(self):
        def target():
            data = (0, 1, 2)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:to_list($stream) -> $output
"""
            )
            return output

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        self.assertEqual(target(), [0, 1, 2])

    def test_stream_simple_reduce(self):
        @apply_operations
        def target():
            data = (0, 1, 2)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:reduce($stream, [$lhs, $rhs] {
    OP $lhs + $rhs
})
STORE $output
"""
            )
            return output

        self.assertEqual(target(), 3)

    def test_stream_simple_reduce_empty(self):
        @apply_operations
        def target():
            data = tuple()
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:reduce($stream, [$lhs, $rhs] {
    OP $lhs + $rhs
})
STORE $output
"""
            )
            return output

        dis.dis(target)

        self.assertEqual(target(), -1)

    def test_stream_simple_reduce_with_start(self):
        @apply_operations
        def target():
            data = (0, 1, 2)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:reduce($stream, [$lhs, $rhs] {
    OP $lhs + $rhs
}, 2)
STORE $output
"""
            )
            return output

        self.assertEqual(target(), 5)

    def test_stream_simple_reduce_with_start_empty(self):
        @apply_operations
        def target():
            data = tuple()
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:reduce($stream, [$lhs, $rhs] {
    OP $lhs + $rhs
}, 2)
STORE $output
"""
            )
            return output

        self.assertEqual(target(), 2)

    def test_stream_simple_filter(self):

        @apply_operations
        def target():
            data = (0, 1, 2)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:filter($stream, [$var] {
    OP $var < 2 -> %
})
std:stream:to_list($stream) -> $output
"""
            )
            return output

        self.assertEqual(target(), [0, 1])

    def test_stream_simple_map(self):
        @apply_operations
        def target():
            data = (0, 1, 2)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:map($stream, [$var] {
    OP $var + 1 -> $var
})
std:stream:to_list($stream) -> $output
"""
            )
            return output

        self.assertEqual(target(), [1, 2, 3])

    def test_stream_grouped(self):
        @apply_operations
        def target():
            data = (0, 1, 2, 3)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:grouped($stream, 2, [_] {})
std:stream:to_list($stream) -> $output
"""
            )
            return output

        dis.dis(target)
        # self.assertEqual(run_code(target), [1, 2, 3])
        self.assertEqual(target(), [[0, 1], [2, 3]])

    def test_stream_grouped_without_handle(self):
        @apply_operations
        def target():
            data = (0, 1, 2, 3)
            stream = None
            output = None
            assembly(
                """
std:stream:initialize($stream)
std:stream:extend($stream, $data)
std:stream:grouped($stream, 2)
std:stream:to_list($stream) -> $output
"""
            )
            return output

        dis.dis(target)

        self.assertEqual(target(), [[0, 1], [2, 3]])

    def test_comprehension_list(self):
        @apply_operations
        def target():
            l = [1, 2, 3, 4]
            assembly("""
std:comprehension:list($l, [$value] { OP $value + 1 -> % }) -> %
RETURN %""")

        self.assertEqual(target(), [2, 3, 4, 5])
