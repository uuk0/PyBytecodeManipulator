
# Version 0.1.10 [upcoming]
- made some instruction configs .json config able
- emulator will crash now with a good exception message when a jump goes out of bounds
- @name_is_static() annotation will now forward the matcher argument correctly
- some of the not documented optimization annotations were changed
- fixed issue with name_is_static() not correctly resolving the name
- fixed issues with some source instr following failing

# Version 0.1.9
- added some more optimizations which do not require annotations, including:
  - unused variable elimination (including unused assignments)
  - reusing values instead of write followed by read
  - eval()-ing some expressions at optimisation time, including when certain things are already known
- refactored the opcode class to be .json-based, so it is more clean
- fixed possible issue when an absolute jump occurs in injected code using capture_local() or similar
- better handling of some cases of capture_local() and similar for parameter detection
- cleaned up insertion code a bit
- made it possible to add hidden instructions for temporary use (e.g. preventing an operation on certain elements)
- changed how insertMethodAt() operates quit a bit, still exposing same API, but inner workings are changed

# Version 0.1.2
- added some infrastructure for working with EXTENDED_ARG opcodes 

# Version 0.1.0 / 0.1.1
    
- Started implementation of the library using python 3.10 as the base
- Supporting basic operations like function inlining, and simple data manipulations
- Added a framework for runtime code optimization on bytecode-level using python annotations for hinting certain stuff
- Added experimental support for python 3.11, tested with alpha 4
- Added cpython_changes.md to keep track of the relevant changes to cpython for the library 
