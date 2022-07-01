import dis
import itertools
import math

import typing

from bytecodemanipulation.OptimiserAnnotations import try_optimise

from bytecodemanipulation.CodeOptimiser import optimise_code

from bytecodemanipulation.util import Opcodes

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper

from bytecodemanipulation.OptimiserAnnotations import builtins_are_static, name_is_static, returns_argument, constant_operation, run_optimisations
from unittest import TestCase


@constant_operation()
def test(a: int):
    return a + 10


class TestSet1(TestCase):
    def setUp(self) -> None:
        run_optimisations()

    def tearDown(self) -> None:
        run_optimisations()

    def test_function_eval(self):
        @builtins_are_static()
        @name_is_static("test", lambda: test)
        def target():
            return test(min(1, 2))

        self.assertEqual(target(), 11)

        run_optimisations()

        self.assertEqual(target(), 11)

        helper = BytecodePatchHelper(target)
        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 11)

        # Result is a "return 11" function

    def test_subtract(self):
        @builtins_are_static()
        @name_is_static("test", lambda: test)
        def target():
            return test(1) - test(-2)

        self.assertEqual(target(), 3)

        run_optimisations()

        self.assertEqual(target(), 3)

        helper = BytecodePatchHelper(target)

        # Remove NOP's we might have left
        optimise_code(helper)

        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 3)

    def test_complex_eval(self):
        @builtins_are_static()
        @name_is_static("test", lambda: test)
        def target():
            return test(test(test(1) - test(-2)) * test(0)) // test(4)

        self.assertEqual(target(), 10)

        run_optimisations()

        self.assertEqual(target(), 10)

        helper = BytecodePatchHelper(target)

        # Remove NOP's we might have left
        optimise_code(helper)

        self.assertEqual(helper.instruction_listing[0].opcode, Opcodes.LOAD_CONST)
        self.assertEqual(helper.instruction_listing[0].argval, 10)

    def test_dict_funcs(self):
        @builtins_are_static()
        def target():
            d = {}
            d.setdefault("test", []).append("Hello World!")
            return d

        self.assertEqual(target(), {"test": ["Hello World!"]})

        run_optimisations()

        self.assertEqual(target(), {"test": ["Hello World!"]})

    def test_builtins_on_real_code(self):
        """
        Copied from mcpython's VertexProvider create method
        """

        CORNER_SIGNS = tuple(itertools.product((-1, 1), repeat=3))
        CUBE_MAP = (
            (6, 2, 3, 7),  # UP
            (5, 1, 0, 4),  # DOWN
            (0, 1, 3, 2),  # LEFT
            (5, 4, 6, 7),  # RIGHT
            (1, 5, 7, 3),  # FRONT
            (4, 0, 2, 6),  # BACK
        )

        @name_is_static("math", lambda: math)
        def rotate_point(point, origin, rotation):
            """
            Helper function for rotating an point around another one
            :param point: the point to rotate
            :param origin: the origin to rotate around
            :param rotation: the rotation angle
            :return: the rotated point

            todo: optimise!
            """
            # code translated from https://stackoverflow.com/questions/13275719/rotate-a-3d-point-around-another-one
            x, y, z = point
            ox, oy, oz = origin
            rx, ry, rz = rotation
            rx = math.pi * rx / 180
            ry = math.pi * ry / 180
            rz = math.pi * rz / 180
            x -= ox
            y -= oy
            z -= oz

            nx = x * math.cos(rz) - y * math.sin(rz)
            ny = x * math.sin(rz) + y * math.cos(rz)
            x, y = nx, ny

            nx = x * math.cos(ry) - z * math.sin(ry)
            nz = x * math.sin(ry) + z * math.cos(ry)
            x, z = nx, nz

            ny = y * math.cos(rx) - z * math.sin(rx)
            nz = y * math.sin(rx) + z * math.cos(rx)
            y, z = ny, nz

            return x + ox, y + oy, z + oz

        @try_optimise()
        @builtins_are_static()
        def calculate_default(size: typing.Tuple[float, float, float]):
            size = tuple(e / 2 for e in size)

            CORNERS = [tuple(e[i] * size[i] for i in range(3)) for e in CORNER_SIGNS]

            return (tuple(CORNERS[i] for i in e) for e in CUBE_MAP)

        @try_optimise()
        @builtins_are_static()
        def offset_data(data, offset: typing.Tuple[float, float, float]):
            return ((tuple(e[i] + offset[i] for i in range(3)) for e in x) for x in data)

        @try_optimise()
        @builtins_are_static()
        def rotate_data(
            data,
            origin: typing.Tuple[float, float, float],
            rotation: typing.Tuple[float, float, float],
        ):
            return ((rotate_point(e, origin, rotation) for e in x) for x in data)

        class Test:
            SHARED = {}

            @classmethod
            @builtins_are_static()
            def target(
                cls,
                offset: typing.Tuple[float, float, float],
                size: typing.Tuple[float, float, float],
                base_rotation_center: typing.Tuple[float, float, float] = None,
                base_rotation: typing.Tuple[float, float, float] = (0, 0, 0),
            ):
                if base_rotation_center is None:
                    base_rotation_center = offset

                # This key defines the VertexProvider instance, so look up this key in the cache
                key = offset, size, base_rotation_center, base_rotation

                # If it exists, we can re-use it
                if key in cls.SHARED:
                    return cls.SHARED[key]

                return cls.SHARED.setdefault(
                    key, cls(offset, size, base_rotation_center, base_rotation)
                )

            @builtins_are_static()
            def __init__(
                self,
                offset: typing.Tuple[float, float, float],
                size: typing.Tuple[float, float, float],
                base_rotation_center: typing.Tuple[float, float, float],
                base_rotation: typing.Tuple[float, float, float],
            ):
                self.offset = offset
                self.size = size
                self.base_rotation = base_rotation
                self.base_rotation_center = base_rotation_center

                self.default = tuple(
                    tuple(e)
                    for e in rotate_data(
                        offset_data(calculate_default(size), offset),
                        base_rotation_center,
                        base_rotation,
                    )
                )

                # The cache is a structure holding
                self.cache: typing.Dict[
                    typing.Tuple[
                        typing.Tuple[float, float, float],
                        typing.Tuple[float, float, float],
                        float,
                    ],
                    typing.Iterable,
                ] = {}

        Test.target((0, 0, 0), (1, 1, 1))

        run_optimisations()

        dis.dis(Test.target)
        dis.dis(Test.__init__)
        dis.dis(offset_data)
        dis.dis(calculate_default)
        dis.dis(rotate_data)

        Test.target((0, 0, 0), (1, 1, 1))


