import typing

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_syntax_error
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


class AssertStaticInstruction(AbstractAssemblyInstruction):
    # ASSERT_STATIC <expression> [<message>]
    NAME = "ASSERT_STATIC"

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

    def emit_bytecodes(
        self, function: MutableFunction, scope: ParsingScope
    ) -> typing.List[Instruction]:
        try:
            value = self.source.evaluate_static_value(scope)
        except NotImplementedError:
            raise throw_positioned_syntax_error(
                scope,
                list(self.source.get_tokens()),
                "Expected <static evaluate-able>",
            ) from None

        if not value:
            try:
                message = (
                    "expected <true-ish value>"
                    if self.text is None
                    else self.text.evaluate_static_value(scope)
                )
            except NotImplementedError:
                message = "expected <true-ish value> (message not arrival)"

            raise throw_positioned_syntax_error(
                scope,
                list(self.source.get_tokens()),
                f"assertion failed: {message}",
                AssertionError,
            )

        return []
