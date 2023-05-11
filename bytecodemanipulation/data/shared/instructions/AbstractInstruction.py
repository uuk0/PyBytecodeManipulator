import typing
from abc import ABC

from bytecodemanipulation.assembler.AbstractBase import IAssemblyStructureVisitable
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.parser import AbstractExpression
from bytecodemanipulation.MutableFunction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


class AbstractAssemblyInstruction(AbstractExpression, IAssemblyStructureVisitable, ABC):
    """
    Abstract base class for assembly instructions

    NAME is the name of the instruction. It must be set when registering the instruction
    to the Parser system

    IMPLEMENTATION will be filled automatically, either with this class,
    or a class implementing this class (so you can create an abstract base for your instruction)
    (this is used in the core instructions, as the bytecode emitter is version dependent, the parsing code
    not)
    """

    NAME: str | None = None
    IMPLEMENTATION: typing.Type["AbstractAssemblyInstruction"] | None = None

    @classmethod
    def register(cls):
        from bytecodemanipulation.assembler.Parser import Parser

        Parser.register(cls)
        return cls

    @classmethod
    def __init_subclass__(cls, **kwargs):
        # copy the class definition into all superclasses inheriting from AbstractAssemblyInstruction
        if ABC not in cls.__bases__:
            for base in cls.__bases__:
                if (
                    issubclass(base, AbstractAssemblyInstruction)
                    and base != AbstractAssemblyInstruction
                    and base.IMPLEMENTATION != base
                ):
                    base.IMPLEMENTATION = cls

            cls.IMPLEMENTATION = cls

    @classmethod
    def consume(
        cls, parser: "Parser", scope: ParsingScope
    ) -> "AbstractAssemblyInstruction":
        """
        Tries to consume the instruction from the token stream in 'parser'
        in the given 'scope', and returns the instruction instance

        TODO: do we want to allow to return multiple instructions without using an CompoundExpression?

        For coders implementing this function: use the throw_positioned_syntax_error(...) function
        for printing fancy error messages with source code location (use e.g. parser[0] for the token)

        :param parser: the Parser instance to use
        :param scope: the ParsingScope to use
        :return: the AbstractAssemblyInstruction instance
        :raises SyntaxError: when syntactically errors occurred
        :raises NameError: when a name is accessed which is not known (e.g. macro names)
        """
        raise NotImplementedError

    def __init__(self, *_, **__):
        raise NotImplementedError

    def fill_scope_complete(self, scope: ParsingScope):
        self.visit_parts(
            lambda e, _: e.fill_scope(scope) if hasattr(e, "fill_scope") else None,
            [],
        )
        return scope

    def fill_scope(self, scope: ParsingScope):
        """
        Method called ahead of any bytecode manipulation in the AST tree,
        to set certain variables in the scope
        """

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        """
        Emits the python bytecode this instruction represents

        :param function: the function object for targeting (used for allocating data in e.g. constant lists during instruction construction)
        :param scope: the parsing scope to use
        :return: a list of instructions
        """
        raise NotImplementedError

    def visit_parts(
        self,
        visitor: typing.Callable[
            [IAssemblyStructureVisitable, tuple, typing.List[AbstractExpression]],
            typing.Any,
        ],
        parents: list,
    ):
        return visitor(self, tuple(), parents)

    def visit_assembly_instructions(
        self, visitor: typing.Callable[[IAssemblyStructureVisitable, tuple], typing.Any]
    ):
        return visitor(self, tuple())

    def get_labels(self, scope: ParsingScope) -> typing.Set[str]:
        return set()
