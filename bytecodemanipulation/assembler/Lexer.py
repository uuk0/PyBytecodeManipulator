import string
import typing
import warnings

try:
    from code_parser.lexers.common import (
        AbstractLexer,
        IntegerToken,
        FloatToken,
        BinaryOperatorToken,
        BracketToken,
        IdentifierToken,
        StringLiteralToken,
        CommentToken,
        AbstractToken,
    )

except ImportError:
    from bytecodemanipulation.assembler.util.tokenizer import (
        AbstractLexer,
        IntegerToken,
        FloatToken,
        BinaryOperatorToken,
        BracketToken,
        IdentifierToken,
        StringLiteralToken,
        CommentToken,
        AbstractToken,
    )


SPECIAL_CHARS = "@$+-~/%?;[]{}()<>=!,.*':§&\\"


class SpecialToken(AbstractToken):
    pass


class PythonCodeToken(AbstractToken):
    pass


def _count_chars_at_end(text: str, c: str) -> int:
    count = 0

    while text.endswith(c):
        text = text.removesuffix(c)
        count += 1

    return count


class Lexer(AbstractLexer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.had_newline = False

    def lex_single(self) -> typing.List[AbstractToken] | AbstractToken | None:
        char = self.inspect()

        self.had_newline = False

        if char == "#":
            token = CommentToken(
                self.consume_until("\n", include=False).removesuffix("\r")
            )
            return token

        if char in string.digits or (
            char == "-" and self.try_inspect_multi(2)[1] in string.digits
        ):
            text = ""
            if self.try_consume("-"):
                text += "."
            text += self.consume_while(string.digits + "_")

            if self.try_inspect() == ".":
                remaining = self.consume(".") + self.consume_while(string.digits + "_")

                if self.try_inspect() and self.try_inspect() in string.ascii_letters:
                    return [
                        IntegerToken(text),
                        SpecialToken("."),
                        IdentifierToken(
                            remaining[1:]
                            + self.consume_while(
                                string.ascii_letters + string.digits + "_"
                            )
                        ),
                    ]

                text += remaining

            elif self.try_inspect() and self.try_inspect() in string.ascii_letters:
                text += self.consume_while(string.ascii_letters + string.digits + "_")

                return IdentifierToken(text)

            return IntegerToken(text)

        if char in string.ascii_letters + "_":
            identifier = self.consume_while(string.ascii_letters + string.digits + "_")

            if identifier == "PYTHON" and self.try_consume_multi(2, " {"):
                python = self.consume_python_code()
                self.consume("}")

                return [IdentifierToken("PYTHON"), PythonCodeToken(python)]

            return IdentifierToken(identifier)

        if char in SPECIAL_CHARS:
            return SpecialToken(self.consume(char))

        if char == '"':
            self.consume(char)
            text = ""

            escape_count = 0
            while (c := self.try_inspect()) and (c != '"' or escape_count % 2 == 1):
                if c == "\\":
                    escape_count += 1
                else:
                    escape_count = 0
                text += c
                self.consume(c)
            self.consume('"')
            return StringLiteralToken(text, '"')

        if char in string.whitespace:
            self.consume_while(string.whitespace)
            return

        raise SyntaxError(f"Invalid char: '{char}' (at {self.cursor})")

    def consume_python_code(self):
        bracket_level = 0

        code = ""

        while True:
            code += self.consume_while(
                string.ascii_letters
                + string.digits
                + string.whitespace
                + "@!$+~*-_.,:;%&/\\[]()<>|"
            )

            n = self.try_inspect()

            if n is None:
                raise SyntaxError("expected '}' at python end, got EOF")

            if n == "#":
                code += self.consume_until("\n")
            elif n in "\"'":
                # todo: f-strings

                if code[-2:] == " f":
                    warnings.warn(
                        "Found f-string in python literal, this might not work!"
                    )

                triple = self.try_inspect_multi(3)

                if triple == n * 3:
                    code += self.consume(triple) + self.consume_until(
                        lambda text, c: text.endswith(triple)
                        and _count_chars_at_end(text.removesuffix(triple), "\\") % 1
                        == 0
                    )
                    pass

                code += self.consume(n) + self.consume_until(
                    lambda text, c: text.endswith(n)
                    and _count_chars_at_end(text.removesuffix(n), "\\") % 1 == 0
                )

            elif n == "{":
                bracket_level += 1

            elif n == "}":
                bracket_level -= 1

                if bracket_level == -1:
                    return code.strip()

            else:
                raise NotImplementedError(n)
