import sys
import typing
import warnings

from bytecodemanipulation.assembler.AbstractBase import AbstractSourceExpression
from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.syntax_errors import PropagatingCompilerException, TraceInfo
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
            raise PropagatingCompilerException(
                "expected <expression>"
            ).add_trace_level(scope.get_trace_info().with_token(parser[0]))

        return cls(
            target,
            parser.try_consume_access_to_value(scope=scope, allow_primitives=True),
            base_token=scope.last_base_token,
            trace_info=scope.get_trace_info(),
        )

    def __init__(
        self, source: AbstractSourceExpression,
        text: AbstractSourceExpression = None,
        base_token: AbstractToken = None,
        trace_info: TraceInfo = None,
    ):
        self.source = source
        self.text = text
        self.base_token = base_token
        self.trace_info = trace_info

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
            print(scope.macro_parameter_namespace_stack)

            raise PropagatingCompilerException(
                "Expected <static evaluate-able> at 'expression'"
            ).add_trace_level(self.trace_info.with_token(self.base_token, list(self.source.get_tokens()))) from None

        if not value:
            try:
                message = (
                    "expected <true-ish value>"
                    if self.text is None
                    else self.text.evaluate_static_value(scope)
                )
            except NotImplementedError:
                print(f"SyntaxWarning: <message> could not be evaluated (got syntax element: {self.text})", file=sys.stderr)
                self.trace_info.with_token(list(self.source.get_tokens())).print_stack(sys.stderr)

                message = "expected <true-ish value> (message not arrival)"

            raise PropagatingCompilerException(
                "assertion failed: " + message
            ).add_trace_level(self.trace_info.with_token(list(self.source.get_tokens()))).set_underlying_exception(AssertionError)

        return []
