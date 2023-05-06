import typing
from abc import ABC

from bytecodemanipulation.assembler.AbstractBase import AbstractAccessExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import AbstractAssemblyInstruction


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser


class AbstractCallAssembly(AbstractAssemblyInstruction, AbstractAccessExpression, ABC):
    INSTANCE: typing.Type["AbstractCallAssembly"] | None = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        AbstractCallAssembly.INSTANCE = cls

    @classmethod
    def construct_from_partial(cls, access: AbstractAccessExpression, parser: "Parser", scope: ParsingScope):
        raise NotImplementedError

    @classmethod
    def consume_macro_call(cls, parser: "Parser", scope: ParsingScope):
        raise NotImplementedError
