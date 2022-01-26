import dis
from unittest import TestCase

from bytecodemanipulation.OptimiserAnnotations import run_optimisations
from bytecodemanipulation.OptimiserAnnotations import builtins_are_static


class TestOptimiserAnnotations(TestCase):
    def test_builtins_are_static_1(self):
        @builtins_are_static()
        def target(a, b):
            return min(a, b)

        self.assertEqual(target(1, 2), 1)

        run_optimisations()
        global min
        min = max

        self.assertEqual(min(1, 2), 2)
        self.assertEqual(target(1, 2), 1)

