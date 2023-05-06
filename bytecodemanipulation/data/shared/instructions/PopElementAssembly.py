import abc

from bytecodemanipulation.assembler.Parser import Parser
from bytecodemanipulation.assembler.util.tokenizer import IntegerToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)


class AbstractPopElementAssembly(AbstractAssemblyInstruction, abc.ABC):
    # POP [<count>]
    NAME = "POP"

    def __init__(self, count):
        self.count = count

    @classmethod
    def consume(cls, parser: "Parser", scope) -> "AbstractPopElementAssembly":
        count = parser.try_consume(IntegerToken)
        return cls(count if count is not None else IntegerToken("1"))

    def __eq__(self, other):
        return type(self) == type(other) and self.count == other.count

    def __repr__(self):
        return f"POP(#{self.count.text})"

    def copy(self) -> "AbstractPopElementAssembly":
        return type(self)(self.count)
