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
        import bytecodemanipulation.assembler.hook as hook

        hook.hook()

        def target():
            assembly(
                """CALL MACRO std:print("Hello World"); CALL MACRO std:print("Hello World", "World Hello!"); CALL MACRO std:print("hello", "world", "test", 123)"""
            )

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()
        target()

    def test_macro_as_assembly(self):
        import bytecodemanipulation.assembler.hook as hook

        hook.hook()

        def target():
            assembly("""std:print("Hello World")""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        target()

    # todo: can we test somehow the input system

    def test_type_check_raise(self):
        import bytecodemanipulation.assembler.hook as hook

        hook.hook()

        def target():
            assembly("""std:check_type(@int, "test", "exception")""")

        mutable = MutableFunction(target)
        apply_inline_assemblies(mutable)
        mutable.reassign_to_function()

        dis.dis(target)

        self.assertRaises(ValueError, target)
