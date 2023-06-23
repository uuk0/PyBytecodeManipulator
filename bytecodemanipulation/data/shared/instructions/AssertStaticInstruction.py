import typing
import warnings

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import print_positional_warning
from bytecodemanipulation.assembler.syntax_errors import throw_positioned_error
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken
from bytecodemanipulation.data.shared.instructions.AbstractInstruction import (
    AbstractAssemblyInstruction,
)
from bytecodemanipulation.opcodes.Instruction import Instruction
from bytecodemanipulation.MutableFunction import MutableFunction


if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.Parser import Parser
    from bytecodemanipulation.data.shared.instructions.AbstractInstruction import AbstractAssemblyInstruction


class AssertStaticInstruction(AbstractAssemblyInstruction):
    # ASSERT_STATIC <expression> [<message>]
    NAME = "ASSERT_STATIC"

    @classmethod
    def consume(cls, parser: "Parser", scope: ParsingScope) -> "AbstractAssertAssembly":
        target = parser.try_consume_access_to_value(scope=scope, allow_primitives=True)

        if target is None:
            raise throw_positioned_error(
                scope, parser[0], "expected <expression>"
            )

        return cls(
            target,
            parser.try_consume_access_to_value(scope=scope, allow_primitives=True),
            base_token=scope.last_base_token,
        )

    def __init__(
        self, source: AbstractSourceExpression,
        text: AbstractSourceExpression = None,
        base_token: AbstractToken = None,
    ):
        self.source = source
        self.text = text
        self.base_token = base_token

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
            print("<target>:", self.source)

            raise throw_positioned_error(
                scope,
                self.base_token or list(self.source.get_tokens()),
                "Expected <static evaluate-able at 'expression'>",
            ) from None

        if not value:
            try:
                message = (
                    "expected <true-ish value>"
                    if self.text is None
                    else self.text.evaluate_static_value(scope)
                )
            except NotImplementedError:
                print_positional_warning(
                    scope,
                    list(self.source.get_tokens()),
                    f"<message> could not be evaluated (got syntax element: {self.text})",
                )

                message = "expected <true-ish value> (message not arrival)"

            raise throw_positioned_error(
                scope,
                list(self.source.get_tokens()),
                f"assertion failed: {message}",
                AssertionError,
            )

        return []
