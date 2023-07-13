import dis
import json
import os
import sys
import unittest

import typing

from bytecodemanipulation.opcodes.Instruction import Instruction

from bytecodemanipulation.Optimiser import BUILTIN_CACHE

from bytecodemanipulation.MutableFunction import MutableFunction
from bytecodemanipulation.Optimiser import _OptimisationContainer


BUILTIN_INLINE = _OptimisationContainer(None)
BUILTIN_INLINE.dereference_global_name_cache.update(BUILTIN_CACHE)

root = os.path.dirname(__file__)


def compare_optimized_results(
    case: unittest.TestCase, target, ideal, opt_ideal=1, msg=...
):
    if hasattr(target, "_debug_wrapper"):
        mutable = target._debug_wrapper
        mutable.reassign_to_function()
    else:
        mutable = MutableFunction(target)

    BUILTIN_INLINE._inline_load_globals(mutable)

    if not hasattr(target, "_debug_wrapper"):
        mutable.reassign_to_function()

    _OptimisationContainer.get_for_target(mutable.target).run_optimisers()

    if opt_ideal > 0:
        mutable = MutableFunction(ideal)
        BUILTIN_INLINE._inline_load_globals(mutable)
        mutable.reassign_to_function()

    dis.dis(ideal)

    if opt_ideal > 1:
        _OptimisationContainer.get_for_target(ideal).run_optimisers()

    mutable = MutableFunction(target)
    mutable2 = MutableFunction(ideal)

    builder_1 = mutable.create_filled_builder()
    builder_2 = mutable2.create_filled_builder()

    eq = len(builder_1.temporary_instructions) == len(builder_2.temporary_instructions)

    if eq:
        eq = all(
            a.lossy_eq(b)
            for a, b in zip(
                builder_1.temporary_instructions, builder_2.temporary_instructions
            )
        )

    if not eq:
        _compare_not_equal_error(mutable, target, ideal)

    case.assertEqual(
        len(builder_1.temporary_instructions),
        len(builder_2.temporary_instructions),
        msg=(msg if msg is not ... else "...") + ": Instruction count !=",
    )

    for a, b in zip(builder_1.temporary_instructions, builder_2.temporary_instructions):
        if isinstance(a.arg_value, Exception):
            case.assertTrue(
                isinstance(b.arg_value, Exception)
                and a.arg_value.args == b.arg_value.args,
                msg=f"{msg if msg is not ... else '...'}: Instruction {a} != {b}",
            )
        else:
            case.assertTrue(
                a.lossy_eq(b),
                msg=f"{msg if msg is not ... else '...'}: Instruction {a} != {b}",
            )


def _compare_not_equal_error(mutable, target, ideal):
    local = os.path.dirname(__file__)
    mutable.dump_info(f"{local}/target.json")
    mutable.dump_info(f"{local}/ideal.json")

    print(f"target ({target.__name__})")
    if hasattr(target, "_debug_wrapper"):
        for instr in target._debug_wrapper.instructions:
            print(instr)
    elif sys.version_info[1] <= 10:
        dis.dis(target)
    else:
        dis.dis(target, show_caches=True)

    print(f"compare ({ideal.__name__})")

    if sys.version_info[1] <= 10:
        dis.dis(ideal)
    else:
        dis.dis(ideal, show_caches=True)


class JsonTestEntry:
    @classmethod
    def from_file(cls, file: str) -> "JsonTestEntry":
        if not os.path.isfile(file):
            file = f"{root}/{file}"

        with open(file) as f:
            return cls.from_data(json.load(f))

    @classmethod
    def from_data(cls, data: dict) -> "JsonTestEntry":
        obj = cls(data["name"])

        if "code" in data:
            if isinstance(data["code"], str):
                obj.code = data["code"]
            else:
                obj.code = [
                    Instruction(
                        e["op"],
                        e.setdefault("arg", None),
                        e.setdefault("rarg", 0),
                    )
                    for e in data["code"]
                ]

            if isinstance(data["compare"], str):
                obj.compare = data["compare"]
            else:
                obj.compare = [
                    Instruction(
                        e["op"],
                        e.setdefault("arg", None),
                        e.setdefault("rarg", 0),
                    )
                    for e in data["compare"]
                ]

        obj.opt_mode = data.setdefault("opt_mode", 1)

        if "items" in data:
            for item in data["items"]:
                item.setdefault("opt_mode", data["opt_mode"])
                obj.add_child(cls.from_data(item))

        return obj

    def __init__(self, name: str):
        self.name = name
        self.code: str | typing.List[Instruction] | None = None
        self.compare: str | typing.List[Instruction] | None = None
        self.children: typing.List[JsonTestEntry] = []
        self.opt_mode = 1

    def add_child(self, child: "JsonTestEntry"):
        self.children.append(child)
        return self

    def run_tests(self, test: unittest.TestCase, prefix: str = ""):
        if self.code:
            if isinstance(self.code, str):
                target = eval(f"lambda: {self.code}")
            else:
                target = self._create_empty_method(self.code)

            if isinstance(self.compare, str):
                compare = eval(f"lambda: {self.compare}")
            else:
                compare = self._create_empty_method(self.compare)

            print(f"running {prefix}:{self.name}")
            compare_optimized_results(
                test,
                target,
                compare,
                opt_ideal=self.opt_mode,
                msg=f"{prefix}:{self.name}",
            )

        for child in self.children:
            child.run_tests(test, f"{prefix}:{self.name}" if prefix else self.name)

    def _create_empty_method(self, c):
        result = lambda: None

        obj = MutableFunction(result)
        obj.assemble_fast(c)
        obj.reassign_to_function()

        return result


BUILTIN_INLINE = _OptimisationContainer(None)
BUILTIN_INLINE.dereference_global_name_cache.update(BUILTIN_CACHE)
