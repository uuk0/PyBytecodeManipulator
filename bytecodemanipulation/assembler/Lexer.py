import string
import typing

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


SPECIAL_CHARS = "@$+-~/%?;[]{}()<>=!,.*"


class SpecialToken(AbstractToken):
    pass


class Lexer(AbstractLexer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.had_newline = False

    def lex_single(self) -> typing.List[AbstractToken] | AbstractToken | None:
        char = self.inspect()

        self.had_newline = False

        if char == "#":
            token = CommentToken(self.consume_until("\n", include=False).removesuffix("\r"))
            return token

        # todo: special tokens

        if char in string.digits or (char == "-" and self.try_inspect_multi(2)[1] in string.digits):
            text = ""
            if self.try_consume("-"):
                text += "."
            text += self.consume_while(string.digits)

            if self.try_inspect() == ".":
                text += self.consume(".") + self.consume_while(string.digits)

            return IntegerToken(text)

        if char in string.ascii_letters + "_":
            identifier = self.consume_while(string.ascii_letters + string.digits + "_")
            return IdentifierToken(identifier)

        if char in SPECIAL_CHARS:
            return SpecialToken(self.consume(char))

        if char == "\"":
            self.consume(char)
            text = ""

            escape_count = 0
            while (c := self.try_inspect()) and (c != "\"" or escape_count % 2 == 1):
                if c == "\\":
                    escape_count += 1
                else:
                    escape_count = 0
                text += c
                self.consume(c)
            self.consume("\"")
            return StringLiteralToken(text, "\"")

        if char in string.whitespace:
            self.consume_while(string.whitespace)
            return

        raise SyntaxError(repr(char))

