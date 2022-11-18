import dis
import unittest

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Optimiser import apply_now


class TestIssue2(unittest.TestCase):
    def test_1(self):
        @apply_now()
        def target(t):
            for x in (0, 1):
                pass



