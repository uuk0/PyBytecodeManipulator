# bytecode:toplevel_static
# bytecode:builtins_protected

import ast
import importlib
import tokenize
import typing
from abc import ABC
from types import ModuleType

from bytecodemanipulation.Optimiser import _OptimisationContainer


def hook():
    """
    import importlib.machinery
    import sys

    # For illustrative purposes only.
    SpamMetaPathFinder = importlib.machinery.PathFinder
    SpamPathEntryFinder = importlib.machinery.FileFinder
    loader_details = (importlib.machinery.SourceFileLoader,
                      importlib.machinery.SOURCE_SUFFIXES)

    # Setting up a meta path finder.
    # Make sure to put the finder in the proper location in the list in terms of
    # priority.
    sys.meta_path.append(SpamMetaPathFinder)

    # Setting up a path entry finder.
    # Make sure to put the path hook in the proper location in the list in terms
    # of priority.
    sys.path_hooks.append(SpamPathEntryFinder.path_hook(loader_details))
    """


class AbstractLevelEntry(ABC):
    pass


class ClassDeclaration(AbstractLevelEntry):
    pass


class FunctionDeclaration(AbstractLevelEntry):
    pass


class ModuleDescription(AbstractLevelEntry):
    """
    @bytecode:guarantee_attribute_type[module, ModuleType]
    """

    def __init__(self, module: ModuleType):
        self.module = module
        self.container = _OptimisationContainer.get_for_target(module)

        self.children: typing.List[AbstractLevelEntry] = []

    def try_parse_toplevel_comment(self, token: tokenize.Token):
        assert token.type == tokenize.COMMENT, "must be comment"


def parse(file: str, module_name: str) -> ModuleType:
    """
    Parses a 'file' (path) as a 'module_name'
    and returns the resulting ModuleType

    @bytecode:guarantee_not_empty[file]
    @bytecode:guarantee_not_empty[module_name]
    """
    with open(file, "rb") as f:
        data = f.read()

        f.seek(0)

        tokens = list(tokenize.tokenize(f.readline))

    ast_tree = ast.parse(data, file)

    module = ModuleType(module_name)
    module_descr = module.__module_descr__ = ModuleDescription(module)

    for token in tokens:
        if token.type in (tokenize.ENCODING, tokenize.NL):
            continue

        elif token.type == tokenize.COMMENT:
            module_descr.try_parse_toplevel_comment(token)

        else:
            break

    return module


if __name__ == "__main__":
    parse(__file__, "__main__")
