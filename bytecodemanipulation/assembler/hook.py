import pathlib
import sys
import importlib
import importlib.machinery
import bytecodemanipulation.assembler.Emitter


class ASMFileFinder(importlib.machinery.SourceFileLoader):
    """
    .pyasm file importer
    so the Emitter is bound to module-level parsing if only the .pyasm file is provided
    """

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
        with open(self.path) as fid:
            asm_code = fid.read()

        bytecodemanipulation.assembler.Emitter.execute_module_in_instance(asm_code, module)

        return module


sys.meta_path.append(ASMFileFinder)

