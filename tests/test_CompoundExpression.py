from unittest import TestCase

from bytecodemanipulation.assembler.target import apply_operations
from bytecodemanipulation.assembler.target import assembly
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException
from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)

from bytecodemanipulation.data.shared.expressions.CompoundExpression import (
    CompoundExpression,
)


# parsing tests happen in other tests


class MockScope:
    scope_path = []


class MockInstruction(AbstractAssemblyInstruction):
    def __init__(self):
        self.fill_scope_value = None

    def fill_scope(self, scope):
        self.fill_scope_value = scope


class TestAssembly(TestCase):
    def test_scope_filling(self):
        mock = MockInstruction()
        mock.fill_scope_value = None

        expr = CompoundExpression([mock])

        scope = MockScope()
        expr.fill_scope_complete(scope)

        self.assertEqual(mock.fill_scope_value, scope)

    def test_visit_assembly_instruction(self):
        mock = MockInstruction()
        mock.fill_scope_value = None

        expr = CompoundExpression([mock])

        found = []

        def visitor(obj, children):
            found.append(obj)

        expr.visit_assembly_instructions(visitor)

        self.assertEqual(found, [mock, expr])
