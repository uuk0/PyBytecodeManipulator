import inspect
import sys
import typing

if typing.TYPE_CHECKING:
    from bytecodemanipulation.assembler.AbstractBase import ParsingScope
from bytecodemanipulation.assembler.util.tokenizer import AbstractToken


def _print_complex_token_location(
    file,
    tokens: typing.List[AbstractToken | None],
):
    while None in tokens:
        tokens.remove(None)

    if not tokens:
        return

    lines: typing.Dict[int, typing.List[AbstractToken]] = {}

    with open(tokens[0].module_file, mode="r", encoding="utf-8") as f:
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

        sections = error_location.rstrip().split(" ")
        error_location = ""
        error_location_2 = ""

        i = 0
        for section in sections:
            error_location += " "
            error_location_2 += " " if i == 0 else "─"

            if section == "":
                continue

            if len(section) == 1:
                error_location += "│"
            else:
                error_location += "╰" + ("─" * (len(section) - 2)) + "┤"

            error_location_2 += (" " if i == 0 else "─") * (len(section) - 1) + ("┴" if i != 0 else "╰")
            i += 1

        error_location = error_location[1:]
        error_location_2 = error_location_2[1:]

        if error_location.count("╰") == 1:
            error_location = f"{error_location[:-1]}┴─"
            error_location_2 = ""
        else:
            error_location_2 += "─"

        if line != previous_line_no + 1:
            if already_seen_line:
                print(file=file)
            already_seen_line = True

            _file = tokens[0].module_file
            print(f'File "{_file}", line {line + 1}', file=file)
        previous_line_no = line

        if previous_line_no >= len(content):
            continue

        print(content[previous_line_no].removesuffix("\n"), file=file)

        if error_location_2:
            print(error_location, file=file)
            print(f"{error_location_2} ", file=file, end="")
        else:
            print(f"{error_location} ", file=file, end="")


class TraceInfo:
    def __init__(self):
        self.tokens = []

    def with_token(
        self, *token: AbstractToken | typing.List[AbstractToken]
    ) -> "TraceInfo":
        instance = TraceInfo()
        instance.with_tokens = self.tokens.copy
        for e in token:
            if isinstance(e, AbstractToken):
                instance.tokens.append(e)
            elif e is not None:
                instance.tokens.extend(e)

        return instance

    def print_stack(self, file=sys.stdout):
        # print(self.tokens)
        _print_complex_token_location(file, self.tokens)


class PropagatingCompilerException(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        self.underlying_exception = SyntaxError
        self.levels: typing.List[typing.Tuple[TraceInfo, str | None]] = []
        self.base_file = inspect.currentframe().f_back.f_code.co_filename
        self.base_lineno = inspect.currentframe().f_back.f_lineno

    def set_underlying_exception(self, exc: typing.Type[Exception]):
        self.underlying_exception = exc
        return self

    def add_trace_level(
        self, info: TraceInfo, message: str = None
    ) -> "PropagatingCompilerException":
        if info is None:
            self.print_exception(file=sys.stderr)
            raise ValueError("info must not be None") from None

        self.levels.append((info, message))
        return self

    def print_exception(self, file=sys.stderr):
        print(f'File "{self.base_file}", line {self.base_lineno}', file=file)

        for trace, message in self.levels:
            trace.print_stack(file=file)

            if message:
                print(message, file=file)
            else:
                print(file=file)
