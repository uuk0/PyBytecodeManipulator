from abc import ABC

from bytecodemanipulation.assembler.AbstractBase import (
    ParsingScope,
    AbstractSourceExpression,
)
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.assembler.Parser import Parser


class AbstractAssertAssembly(AbstractAssemblyInstruction, ABC):
    # ASSERT <expression> [<message>]
    NAME = "ASSERT"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "AbstractAssertAssembly":
        target = parser.try_consume_access_to_value(scope=scope, allow_primitives=True)

        if target is None:
            raise throw_positioned_syntax_error(
                scope, parser[0], "expected <expression>"
            )

        return cls(
            target,
            parser.try_consume_access_to_value(scope=scope, allow_primitives=True),
        )

    def __init__(
        self, source: AbstractSourceExpression, text: AbstractSourceExpression = None
    ):
        self.source = source
        self.text = text

    def __repr__(self):
        return f"ASSERT({self.source}, {self.text})"

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.source == other.source
            and self.text == other.text
        )

    def copy(self):
        return type(self)(self.source.copy(), self.text.copy() if self.text else None)
