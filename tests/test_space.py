import itertools
import string

INVOKED = 0


def test_for_invoke():
    global INVOKED
    INVOKED += 1


async def test_for_invoke_async():
    global INVOKED
    INVOKED += 1


def create_big_function():
    chars = "abcdefghijklmnopqrstuvwxyz"

    names = itertools.product(chars, chars)
    func_code = "\n    ".join(f"{''.join(name)}_ = 0" for name in names)

    code = f"""
def test():
    {func_code}"""

    scope = {}

    exec(code, globals(), scope)
    return scope["test"]
