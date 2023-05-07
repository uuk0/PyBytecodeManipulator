import abc
import typing
from bytecodemanipulation.assembler.util.tokenizer import (
    AbstractToken,
    IntegerToken,
    BinaryOperatorToken,
    BracketToken,
    IdentifierToken,
    EndOfFileToken,
)
from .CommonUtil import AbstractCursorStateItem


class AbstractExpression(abc.ABC):
    def visit_topdown(
        self,
        visitor: typing.Callable[["AbstractExpression", "AbstractExpression"], None],
        previous=None,
    ):
        visitor(self)

    def visit_depth_first(
        self,
        visitor: typing.Callable[["AbstractExpression", "AbstractExpression"], None],
        previous=None,
    ):
        visitor(previous, self)

    def copy(self) -> "AbstractExpression":
        raise NotImplementedError

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self):
        return self.copy()

    def replace_inner(
        self, node: "AbstractExpression", replacement: "AbstractExpression"
    ):
        raise ValueError(node)


class NumericExpression(AbstractExpression):
    def __init__(self, token: IntegerToken | str):
        self.token = token if isinstance(token, IntegerToken) else IntegerToken(token)

    def __eq__(self, other):
        return type(other) == type(self) and self.token == other.token

    def __repr__(self):
        return f"IntegerExpression({self.token})"

    def copy(self) -> "NumericExpression":
        return NumericExpression(self.token)


class BracketExpression(AbstractExpression):
    def __init__(
        self,
        left_bracket: BracketToken | str,
        inner: AbstractExpression,
        right_bracket: BracketToken | str = None,
    ):
        self.left_bracket = (
            left_bracket
            if isinstance(left_bracket, BracketToken)
            else BracketToken(left_bracket)
        )
        self.inner = inner
        self.right_bracket = (
            (
                right_bracket
                if isinstance(right_bracket, BracketToken)
                else BracketToken(right_bracket)
            )
            if right_bracket
            else BracketToken(self.left_bracket.get_other())
        )

    def visit_topdown(
        self,
        visitor: typing.Callable[["AbstractExpression", "AbstractExpression"], None],
        previous=None,
    ):
        visitor(previous, self)
        self.inner.visit_topdown(visitor, self)

    def visit_depth_first(
        self,
        visitor: typing.Callable[["AbstractExpression", "AbstractExpression"], None],
        previous=None,
    ):
        self.inner.visit_depth_first(visitor, self)
        visitor(previous, self)

    def replace_inner(
        self, node: "AbstractExpression", replacement: "AbstractExpression"
    ):
        if id(node) == id(self.inner):
            self.inner = replacement
        else:
            raise ValueError(node)

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.left_bracket == other.left_bracket
            and self.inner == other.inner
            and self.right_bracket == other.right_bracket
        )

    def __repr__(self):
        return f"BracketExpression({self.left_bracket}, {self.inner}, {self.right_bracket})"

    def copy(self):
        return BracketExpression(
            self.left_bracket,
            self.inner.copy(),
            self.right_bracket,
        )


class BinaryExpression(AbstractExpression):
    def __init__(
        self,
        lhs: AbstractExpression,
        operator: BinaryOperatorToken | str,
        rhs: AbstractExpression,
    ):
        self.lhs = lhs
        self.operator = (
            operator
            if isinstance(operator, BinaryOperatorToken)
            else BinaryOperatorToken(operator)
        )
        self.rhs = rhs

    def visit_topdown(
        self,
        visitor: typing.Callable[["AbstractExpression", "AbstractExpression"], None],
        previous=None,
    ):
        visitor(previous, self)
        self.lhs.visit_topdown(visitor, self)
        self.rhs.visit_topdown(visitor, self)

    def visit_depth_first(
        self,
        visitor: typing.Callable[["AbstractExpression", "AbstractExpression"], None],
        previous=None,
    ):
        self.lhs.visit_depth_first(visitor, self)
        self.rhs.visit_depth_first(visitor, self)
        visitor(previous, self)

    def replace_inner(
        self, node: "AbstractExpression", replacement: "AbstractExpression"
    ):
        if id(node) == id(self.lhs):
            self.lhs = replacement
        elif id(node) == id(self.rhs):
            self.rhs = replacement
        else:
            raise ValueError(node)

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.lhs == other.lhs
            and self.operator == other.operator
            and self.rhs == other.rhs
        )

    def __repr__(self):
        return f"BinaryExpression({self.lhs}, {self.operator}, {self.rhs})"

    def copy(self):
        return BinaryExpression(self.lhs.copy(), self.operator, self.rhs.copy())


class IdentifierExpression(AbstractExpression):
    def __init__(self, token: IntegerToken | str):
        self.token = (
            token if isinstance(token, IdentifierToken) else IdentifierToken(token)
        )

    def __eq__(self, other):
        return type(other) == type(self) and self.token == other.token

    def __repr__(self):
        return f"IdentifierExpression({self.token})"

    def copy(self) -> "IdentifierExpression":
        return IdentifierExpression(self.token)


def raise_syntax_error(token: AbstractToken, message: str, arg):
    raise SyntaxError(f"{token}: {message}")


class AbstractParser(AbstractCursorStateItem, abc.ABC):
    def __init__(self, tokens: typing.List[AbstractToken]):
        super().__init__()
        self.tokens = tokens

    def __getitem__(
        self, item: int | slice
    ) -> AbstractToken | typing.List[AbstractToken] | None:
        if isinstance(item, int):
            index = self.cursor + item

            if index < 0 or index >= len(self.tokens):
                return

            return self.tokens[index]

        elif isinstance(item, slice):
            start = self.cursor + item.start
            stop = (self.cursor + item.stop) if item.stop else None
            step = item.step if item.step is not None else 1

            if (
                start < 0
                or start >= len(self.tokens)
                or stop < 0
                or stop >= len(self.tokens)
            ):
                return

            return self.tokens[start:stop:step]

        raise IndexError(item)

    def is_empty(self) -> bool:
        return len(self.tokens) == self.cursor + 1

    def assert_EOF(self):
        if not self.is_empty():
            raise SyntaxError("EOF expected")

    def inspect(self, eof_allowed=False) -> AbstractToken:
        if self.is_empty():
            raise SyntaxError("EOF reached!")

        token = self.tokens[self.cursor]

        if isinstance(token, EndOfFileToken) and not eof_allowed:
            raise SyntaxError("EOF reached!")

        return token

    def try_inspect(self, eof_allowed=False) -> AbstractToken | None:
        if self.is_empty():
            return

        token = self.tokens[self.cursor]

        if isinstance(token, EndOfFileToken) and not eof_allowed:
            return

        return token

    T = typing.TypeVar(
        "T", AbstractToken, typing.List[typing.Type[AbstractToken] | AbstractToken]
    )

    def consume(self, expected: T | typing.Type[T] = None, err_arg=None) -> T:
        """
        Consumes a token and compares it against the 'expected' (which is an instance or the expected type of token)

        :return: the parsed token
        :raises SyntaxError: if it failed to parse the token (either invalid type or end of stream)
        """
        token: AbstractToken = self.inspect()

        if expected:
            if isinstance(expected, AbstractToken):
                if token != expected:
                    raise_syntax_error(token, f"Expected {expected}", err_arg)
                    raise SyntaxError

            elif isinstance(expected, list):
                for element in expected:
                    if isinstance(element, AbstractToken):
                        if token == element:
                            break
                    else:
                        if isinstance(token, element):
                            break
                else:
                    raise SyntaxError(
                        f"Expected any of {repr(list(expected))[1:-1]}, got {token} (at token token position: {self.cursor+1})"
                    )

            else:
                if not isinstance(token, expected):
                    raise SyntaxError(
                        f"Expected type {expected.__name__}, got {token} (type: {type(token).__name__})"
                    )

        self.cursor += 1

        return token

    def try_consume(self, expected: T | typing.Type[T] = None) -> T | None:
        """
        Tries to consume a token from the token stream

        :param expected: the expected type of token, either instance or type
        :return: the consumed token or None
        """
        token: AbstractToken = self.try_inspect()

        if token is None:
            return

        if expected:
            if isinstance(expected, AbstractToken):
                if token != expected:
                    return

            elif isinstance(expected, (list, tuple)):
                for element in expected:
                    if isinstance(element, AbstractToken):
                        if token == element:
                            break
                    else:
                        if isinstance(token, element):
                            break
                else:
                    return
            else:
                if not isinstance(token, expected):
                    return

        self.cursor += 1

        return token

    def try_consume_multi(
        self, elements: typing.List[T | typing.Type[T]]
    ) -> typing.List[T] | None:
        """
        Tries to consume multiple tokens at ones, and fails completely if any fails to be parsed

        :param elements: the stuff to be parsed, like the parameters to try_consume(...)
        :return: a list of tokens, or None in case of a parsing error
        """

        self.save()
        parsed: typing.List[AbstractParser.T | typing.Type[AbstractParser.T]] = []

        for element in elements:
            if expr := self.try_consume(element):
                expr: AbstractParser.T | typing.Type[AbstractParser.T]
                parsed.append(expr)
                continue

            self.rollback()
            return

        self.discard_save()
        return parsed

    def parse(self) -> AbstractExpression:
        raise NotImplementedError
