import importlib
import json
import logging
import os
import sys
from bytecodemanipulation.Opcodes import Opcodes, init_maps, OPNAME2CODE
from bytecodemanipulation import Opcodes as OpcodesM
from bytecodemanipulation.annotated_std import CONSTANT_BUILTINS


local = os.path.dirname(__file__)

version = f"{sys.version_info.major}_{sys.version_info.minor}"
folder = local + "/data/v" + version
sys.path.append(os.path.dirname(local))


INIT_ASSEMBLY = True


def load_opcode_data():
    opcode_data: dict = json.load(open(folder + "/opcodes.json"))

    valid_opcode_names = [
        key
        for key, value in Opcodes.__dict__.items()
        if isinstance(value, int) and not key.startswith("__") and value < 256
    ]

    for key, opcode in opcode_data.items():
        if key not in valid_opcode_names:
            logging.warning(f"unknown opcode name encountered: {key} - Adding manually")

        setattr(Opcodes, key, opcode)

    for key in valid_opcode_names:
        if key not in opcode_data:
            setattr(Opcodes, key, -1)


def load_instruction_spec():
    spec_data = json.load(open(folder + "/instruction_spec.json"))

    for key, opcodes in spec_data.items():
        getattr(OpcodesM, key)[:] = map(OPNAME2CODE.__getitem__, opcodes)


def load_builtin_spec():
    import builtins
    from bytecodemanipulation.annotated_std import CONSTANT_BUILTINS
    from bytecodemanipulation.annotated_std import CONSTANT_BUILTIN_TYPES

    builtin_spec = json.load(open(folder + "/builtins.json"))

    CONSTANT_BUILTINS[:] = [getattr(builtins, key) for key in builtin_spec["constant"]]
    CONSTANT_BUILTIN_TYPES[:] = [
        getattr(builtins, key) for key in builtin_spec["const_builtin_types"]
    ]

    importlib.import_module("bytecodemanipulation.data.v" + version + ".specialize")


def load_standard_library_annotations():
    import importlib

    std_annot = json.load(open(folder + "/standard_library.json"))

    for module_name, data in std_annot.items():
        module = importlib.import_module(module_name)

        for name in data.setdefault("constant", []):
            attr = module
            for e in name.split("."):
                attr = getattr(attr, e)

            CONSTANT_BUILTINS.append(attr)


ASSEMBLY_MODULE = {}


def load_assembly_instructions():
    if os.path.exists(folder + "/assembly_instructions.py"):
        # exec(open(folder + "/assembly_instructions.py").read(), ASSEMBLY_MODULE)
        ASSEMBLY_MODULE.update(
            importlib.import_module(
                "bytecodemanipulation.data.v" + version + ".assembly_instructions"
            ).__dict__
        )


def init():
    load_opcode_data()
    init_maps()
    load_instruction_spec()
    load_builtin_spec()
    load_standard_library_annotations()

    if INIT_ASSEMBLY:
        load_assembly_instructions()
