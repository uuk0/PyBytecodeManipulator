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

Replacing a code constant (in the whole function body):
```python
from bytecodemanipulation.Transformers import TransformationHandler

handler = TransformationHandler()


def test():
  return 0


handler.makeFunctionArrival("test", test)

# Replaces the constant '0' from the return with a '1'
handler.replace_method_constant("test", 0, 1)

handler.applyTransforms()

assert test() == 1
```

We can also select single constants, like the following:
```python
from bytecodemanipulation.Transformers import TransformationHandler
from bytecodemanipulation.InstructionMatchers import CounterMatcher

handler = TransformationHandler()


def test():
  print(0)
  return 0


handler.makeFunctionArrival("test", test)

# Replaces the constant '0' from the return with a '1'
handler.replace_method_constant("test", 0, 1, matcher=CounterMatcher(1, 1))

handler.applyTransforms()

# This will return 1, but print 0
assert test() == 1
```


## Code Formatting

We use the python formatting library "black" on our code

