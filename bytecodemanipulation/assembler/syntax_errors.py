import sys
import typing

from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken


def _print_complex_token_location(
    scope: ParsingScope,
    tokens: typing.List[AbstractToken | None],
    exc_type: typing.Type[Exception] = SyntaxError,
):
    lines: typing.Dict[int, typing.List[AbstractToken]] = {}

    with open(scope.module_file, mode="r", encoding="utf-8") as f:
        content = f.readlines()

    for token in tokens:
        if token:
            lines.setdefault(token.line, []).append(token)

    already_seen_line = False
    previous_line_no = -2

    for line in sorted(list(lines.keys())):
        tokens = lines[line]
        tokens.sort(key=lambda t: t.column)

        error_location = ""

        for token in tokens:
            if token.column > len(error_location):
                error_location += " " * (token.column - len(error_location))

            delta = len(error_location) - token.column

            if delta >= token.span:
                continue

            error_location += "^" + ("~" * (token.span - delta))

        error_location = error_location.replace("^^", "^~").replace("~^", "~~")

        if line != previous_line_no + 1:
            if already_seen_line:
                print()
            already_seen_line = True

            file = scope.module_file.replace("\\", "/")
            print(f'File "{file}", line {line + 1}', file=sys.stderr)
        previous_line_no = line

        print(content[line].removesuffix("\n"), file=sys.stderr)
        print(error_location, file=sys.stderr)


def throw_positioned_syntax_error(
    scope: ParsingScope,
    token: AbstractToken | typing.List[AbstractToken | None] | None,
    message: str,
    exc_type: typing.Type[Exception] = SyntaxError,
) -> Exception:
    print("at", token, file=sys.stderr)
    if scope and scope.module_file and token:
        if isinstance(token, list):
            _print_complex_token_location(scope, token, exc_type=exc_type)
        else:
            file = scope.module_file.replace("\\", "/")
            print(f'File "{file}", line {token.line+1}', file=sys.stderr)
            with open(scope.module_file, mode="r", encoding="utf-8") as f:
                content = f.readlines()

            line = content[token.line]
            print(line.rstrip(), file=sys.stderr)
            print(
                (" " * token.column) + "^" + ("~" * (token.span - 1)), file=sys.stderr
            )

        print(f"-> {exc_type.__name__}: {message}", file=sys.stderr)
    else:
        # print(scope, scope.module_file if scope else None, token)
        return exc_type(f"{token}: {message}")

    return exc_type(message)


def _syntax_wrapper(token, text, scope):
    raise throw_positioned_syntax_error(scope, token, text)
