# PyBytecodeManipulator
A high level python bytecode manipulation library

Supports code inlining, branch removing, arbitrary code injection into 
existing functions, and a lot more.

WARNING: using bytecode manipulation on a so low level as we do can break 
the python runtime at any point without a warning. We circumvent a lot of 
safety checks normally done. 

WARNING: We cannot make sure that everything works as it should, expect broken code 
at runtime!


Supported python versions:

- 3.9 and below: unsupported; will produce syntax errors due to using new features
- 3.10 (main development)
- 3.11[a4] (forward porting; WIP)

Other version may work, but due to possible internal changes, we do not recommend using 
them together with this library!

## Why are there so many print()-s?

Due to the breaking nature of anything this touches, and the absents of traces 
at the function itself, we decided to add a lot of "debug" statements indicating 
mostly the who-has-done-what-to-which-method for the runtime. 

If you want them removed, create your own Fork of this and remove them, on your own risk

## Compatibility with other libraries 

- Nuitka (https://github.com/Nuitka/Nuitka): Incompatible; will break as nuitka removes the \_\_code__ attribute 
  we modify


# Examples

Replacing a code constant (globally):
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
