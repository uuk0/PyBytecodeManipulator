import abc
import typing
from collections import namedtuple

from .CommonUtil import AbstractCursorStateItem


class AbstractToken(abc.ABC):
    __slots__ = ("text", "line", "column", "span")

    def __init__(self, text: str):
        self.text = text
        self.line: int | None = None
        self.column: int | None = None
        self.span: int | None = None

    def __eq__(self, other):
        return type(other) == type(self) and self.text == other.text

    def __repr__(self):
        return f"{type(self).__name__}({repr(self.text)})"

    def __hash__(self):
        return hash((type(self).__name__, self.text))


class IntegerToken(AbstractToken):
    pass


class FloatToken(AbstractToken):
    pass


class BinaryOperatorToken(AbstractToken):
    pass


class BracketToken(AbstractToken):
    def is_opening(self) -> bool:
        return self.text in "([{<"

    def get_other(self) -> str:
        match self.text:
            case "(":
                return ")"
            case ")":
                return "("
            case "[":
                return "]"
            case "]":
                return "["
            case "{":
                return "}"
            case "}":
                return "{"
            case "<":
                return ">"
            case ">":
                return "<"

        raise NotImplementedError


class IdentifierToken(AbstractToken):
    pass


class CommentToken(AbstractToken):
    pass


class StringLiteralToken(AbstractToken):
    __slots__ = ("text", "quotes")

    def __init__(self, string: str, quotes: str):
        super().__init__(string)
        self.quotes = quotes

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.text == other.text
            and self.quotes == other.quotes
        )

    def __repr__(self):
        return f"{type(self).__name__}({repr(self.text)}, {self.quotes})"


class EndOfFileToken(AbstractToken):
    def __init__(self):
        super().__init__("")


class AbstractLexer(AbstractCursorStateItem, abc.ABC):
    """
    Base class for Lexers (also known as Tokenizers)

    Contains handling code for a linear tokenizer,
    and functions for collecting text easily.
    """

    INCLUDE_LINE_INFO = True

    def __init__(self, text: str, initial_line_offset=0):
        super().__init__()
        self.text = text
        self.old_line_number = 1
        self.old_column_number = 0
        self._line_offset = initial_line_offset

    def add_line_offset(self, offset: int):
        self._line_offset += offset
        return self

    def is_empty(self) -> bool:
        """
        Checks if no text is left to visit
        """
        return len(self.text) <= self.cursor

    def assert_EOF(self):
        """
        asserts that EOF is reached

        :raises SyntaxError: if EOF is not reached
        """
        if not self.is_empty():
            raise SyntaxError("EOF expected")

    def inspect(self) -> str:
        """
        Returns the current char the cursor is at

        :raises SyntaxError: when the cursor is outside the bounds of the text
        """
        if self.is_empty():
            raise SyntaxError("EOF reached!")

        return self.text[self.cursor]

    def try_inspect_multi(self, count: int) -> str | None:
        if len(self.text) < self.cursor + count:
            return

        return self.text[self.cursor : self.cursor + count]

    def try_inspect(self) -> str | None:
        """
        Returns the current char the cursor is at, or None
        """
        if self.is_empty():
            return

        return self.text[self.cursor]

    def consume(self, expected: str = None) -> str:
        """
        Returns the current char the cursor is at, and increments the cursor

        :raises SyntaxError: when the cursor is outside the bounds of the text
        """
        t = self.inspect()

        if expected and t not in expected:
            raise SyntaxError(
                f"Expected any of {repr(list(expected))[1:-1]}, got '{t}' (at position {self.cursor+1})"
            )

        self.cursor += 1
        return t

    def consume_multi(self, count: int, expected: str = None):
        t = self.try_inspect_multi(count)

        if expected and t not in expected:
            raise SyntaxError(
                f"Expected any of {repr(list(expected))[1:-1]}, got {t} (at position {self.cursor + 1})"
            )

        self.cursor += count
        return t

    def try_consume(self, expected: str = None) -> str | None:
        """
        Returns the current char the cursor is at and increments the cursor, or None
        """
        t = self.try_inspect()

        if t is None or (expected and t not in expected):
            return

        self.cursor += 1
        return t

    def try_consume_multi(self, count: int, expected: str = None) -> str | None:
        t = self.try_inspect_multi(count)

        if t is None or (expected and t not in expected):
            return

        self.cursor += count
        return t

    def consume_while(self, predicate: typing.Callable[[str, str], bool] | str):
        """
        Consumes chars while predicate(text, char) returns True

        :param predicate: the predicate
        """
        if isinstance(predicate, str):
            options = set(predicate)
            predicate = lambda _, char: char in options

        text = ""

        while not self.is_empty() and predicate(text, self.inspect()):
            text += self.consume()

        return text

    def consume_until(
        self, predicate: typing.Callable[[str, str], bool] | str, include=True
    ):
        """
        Consumes chars while predicate(text, char) returns False

        :param predicate: the predicate
        :param include: if to include when the predicate is met
        """
        if isinstance(predicate, str):
            options = set(predicate)
            predicate = lambda _, char: char in options

        text = ""

        while not self.is_empty() and not predicate(text, self.inspect()):
            text += self.consume()

        if include:
            text += self.consume()

        return text

    def lex(self) -> typing.List[AbstractToken]:
        """
        Lex-es the text the object was constructed from.
        Returns the list of tokens.
        """
        skipped = 0
        self.old_column_number = 0

        tokens = []
        while not self.is_empty():
            old_cursor = self.cursor

            try:
                result = self.lex_single()
            except SyntaxError:
                print(tokens)
                raise

            if self.cursor == old_cursor:
                print(result, tokens)
                raise RuntimeError("Lexer did not increment cursor!")

            if result is None:
                skipped += self.cursor - old_cursor
                self.old_column_number += self.cursor - old_cursor
                continue

            if self.INCLUDE_LINE_INFO:
                partial = self.text[old_cursor - skipped : self.cursor]
                whitespace_count = len(partial) - len(partial.lstrip())

                self.old_line_number += partial.count("\n")
                if "\n" in partial[:whitespace_count]:
                    self.old_column_number = len(partial.split("\n")[-1]) - len(
                        partial.split("\n")[-1].lstrip()
                    )

                for r in result if isinstance(result, list) else (result,):
                    newline_count = partial[:whitespace_count].count("\n")
                    r.line = self.old_line_number + self._line_offset
                    r.column = self.old_column_number - newline_count
                    r.span = self.cursor - old_cursor

                    # print(
                    #     f"parsed string '{repr(partial)[1:-1]}' (line: {r.line}, column: {r.column}, span: {r.span})"
                    # )

                    self.old_column_number += r.span

                skipped = 0

            if isinstance(result, list):
                tokens += result
            else:
                tokens.append(result)

        tokens.append(EndOfFileToken())

        return tokens

    def lex_single(self) -> typing.List[AbstractToken] | AbstractToken | None:
        raise NotImplementedError()
