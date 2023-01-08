import os


try:
    if os.environ["BYTECODEMANIPULATION_ENABLE_SELF_OPTIMISE"]:
        import bytecodemanipulation.optimise_self
except KeyError:
    pass
