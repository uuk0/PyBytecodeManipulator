# PyBytecodeManipulator
A high level cross-version python bytecode manipulation library build ontop
of 'dis' and 'inspect'

Supports code inlining, branch removing and arbitrary code injection into
existing functions.

WARNING: using bytecode manipulation on a so low level as we do can break
the python runtime at any point without a warning. We circumvent a lot of
safety checks normally done.

WARNING: We cannot make sure that everything works as it should, expect broken code
at runtime!


Supported python versions:

- 3.10 (main development)
- 3.11.0[b3] (forward porting; WIP; Currently not working)

Other versions will not work as a lot of config is stored in .json files per-version,
so you may need to provide your own .json config files for the version you need.

(Some versions might be plug-and-play, but most will require code changes additionally)

## Why are there so many print()-s?

Due to the breaking nature of anything this code touches, and the absents of any traces
in the function itself, we decided to add a lot of "debug" statements indicating
mostly the who-has-done-what-to-which-method for the runtime.
This makes debugging broken code easier, as it is more clear what happened to each transformed function.

If you want them removed, create your own Fork of this and remove them, on your own risk.

We may use in the future the logging library, so you can disable our logger instance, but we
are currently in an inter-stage of the code, so other stuff has priority.

## Compatibility with other libraries

- Nuitka (https://github.com/Nuitka/Nuitka): Incompatible; will break as nuitka removes the \_\_code__ attribute
  we modify
- Other bytecode modification / analysers: Should work as long as you as the user does NOT expose intermediate
  results which might contain internal instructions


## Debugging your injections

There is the possibility to "debug" functions using the execution emulator.
It will be able to give you more information about a crash than the python core interpreter,
but will be a lot slower than it.

It comes also with the possibility to run your bytecode in another interpreter version, so
you can experiment with some stuff.
In theory, it is also possible to run in python versions not supported by the
bytecode manipulation system, but it is not recommended.

TransformationHandler() takes as an arg debug_code and debug_further_calls
for activating it for all accessed methods.

BytecodePatchHelper() contains a method enable_verbose_exceptions() for activating it on
that exact method.


# Examples

Replacing global access with constant value

```python
from bytecodemanipulation.Optimiser import cache_global_name, apply_now

@cache_global_name("min", lambda: min)
def test(x, y):
    return min(x, y)

apply_now(test)
```

Inlining method calls

```python
from bytecodemanipulation.Optimiser import cache_global_name, inline_calls, apply_now

@inline_calls
def call(a, b):
    return a + b

@cache_global_name("call", lambda: call)
def test(x, y):
    return call(x, y)

apply_now(test)
```

will result in bytecode which could be represented with:

```python
def test(x, y):
    return x + y
```

(there might be extra local variables generated for parameters)

# Applied Optimisations

- Constant Expression inlining (can be declared for custom functions to be constant)
- LOAD_GLOBAL for builtins (if enabled)
- standard library inlining (if enabled)
- specialization of methods based on arguments, e.g. constant arguments (when already resolved before, requires one of above options)
- branch elimination when jumping on a constant (TODO: also if condition can be inferred ahead-of-time, see specialization)
- local variable elimination (TODO: add more cases)


# Currently Limitations

- Line Numbers get mixed up, we need some way to assign meaningful line numbers
- With python 3.11, exception table exists, and this breaks our current concept of one big flow diagram,
  as exception handling code might exist outside the default flow
- Also python 3.11 introduces CACHE-s for instructions, which will require some work in order to work
- During optimization, a lot of stuff is being recomputed each optimization pass, we need to cache that drastically
- Method inlining is not working properly and needs a lot more testing (WIP)
- If the exact type is known at optimisation time (e.g. object creation via class call, or type annotation), we can try to
  inline method accesses for further optimisation
- Python 3.12 will likely break how certain operations are stored in instructions, combing opcodes-without-args into a single
  parent instruction, using the arg to switch between modes


# Assembly Code

- The library provides also a way to use some "python-assembly" for writing code
- This is only python bytecode, so no fancy stuff can be done
- See ASSEMBLY.md for more information on instructions
- We provide an import system hook for importing .pyasm files via bytecodemanipulation.assembler.hook
- You may use the functions from bytecodemanipulation.assembler.target for creating inline-assembly
    - assembly(\<code>) can be used for inline assembly
    - this also includes macro, which may be also created from python-defined methods


# Code Formatting

We use the python formatting library "black" on our code

# TODO's

- abstract opcode affect away into a .json file describing all opcodes
- create a json file for defining certain bytecode sequences
- write more library-specific optimisations
- write generating bytecode system for emulator, constructing a function pointing to the
  .json file for exception printing, and optimizing wherever possible
- add optimisation: JUMP on condition for some operators (e.g. NOT)

