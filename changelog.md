
# Version 0.1.3 [upcoming]
- added some more optimizations which do not require annotations, including:
  - unused variable elimination (including unused assignments)
  - reusing values instead of write followed by read
  - eval()-ing some expressions at optimisation time, including when certain things are already known

# Version 0.1.2
- added some infrastructure for working with EXTENDED_ARG opcodes 

# Version 0.1.0 / 0.1.1
    
- Started implementation of the library using python 3.10 as the base
- Supporting basic operations like function inlining, and simple data manipulations
- Added a framework for runtime code optimization on bytecode-level using python annotations for hinting certain stuff
- Added experimental support for python 3.11, tested with alpha 4
- Added cpython_changes.md to keep track of the relevant changes to cpython for the library 
