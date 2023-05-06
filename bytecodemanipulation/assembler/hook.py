import pathlib
import sys
import importlib
import importlib.machinery
import types

import typing

from bytecodemanipulation.assembler import Emitter


class ASMFileFinder(importlib.machinery.SourceFileLoader):
    """
    .pyasm file importer
    so the Emitter is bound to module-level parsing if only the .pyasm file is provided
    """

    MODULE_CACHE: typing.Dict[str, types.ModuleType] = {}

    @classmethod
    def find_spec(cls, name, path, target=None):
        package, _, module_name = name.rpartition(".")

        asm_file_name = f"{module_name}.pyasm"

        directories = sys.path if path is None else path

        for directory in directories:

            csv_path = pathlib.Path(directory) / asm_file_name

            if csv_path.exists():
                return importlib.machinery.ModuleSpec(name, cls(name, str(csv_path)))

        return None

    def exec_module(self, module):
        if module.__name__ in self.MODULE_CACHE:
            return self.MODULE_CACHE[module.__name__]

        self.MODULE_CACHE[module.__name__] = module

        with open(self.path, encoding="utf-8") as fid:
            asm_code = fid.read()

        Emitter.execute_module_in_instance(asm_code, module, self.path)

        return module


def hook():
    if ASMFileFinder not in sys.meta_path:
        sys.meta_path.append(ASMFileFinder)


def unhook():
    if ASMFileFinder in sys.meta_path:
        sys.meta_path.remove(ASMFileFinder)


hook()
