import os.path
import time
from unittest import TestCase
import dis

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.assembler.target import *
from bytecodemanipulation.assembler.Emitter import apply_inline_assemblies


class StandardLibraryTest(TestCase):
    def setUp(self):
        import bytecodemanipulation.assembler.hook as hook

        hook.hook()

        def target():
            assembly("""MACRO_IMPORT bytecodemanipulation.standard_library""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        target()

    def test_macro_import(self):
        def target():
            assembly(
                """CALL MACRO std:print("Hello World"); CALL MACRO std:print("Hello World", "World Hello!"); CALL MACRO std:print("hello", "world", "test", 123)"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()
        target()

    def test_macro_as_assembly(self):
        def target():
            assembly("""std:print("Hello World")""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        target()

    # todo: can we test somehow the input system

    def test_type_check_raise(self):
        def target():
            assembly("""std:check_type(@int, "test", "exception")""")

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
        self.assertEqual(set(files), set(filter(lambda e: os.path.isfile(e), os.listdir(os.path.dirname(__file__)))))
