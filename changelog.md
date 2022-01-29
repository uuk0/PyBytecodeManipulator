
# Version 0.1.2
- added some infrastructure for working with EXTENDED_ARG opcodes 
- rewritten the re-assembler of the instructions into the real bytecode 
  - EXTENDED_ARG opcodes are now skipped during disassembly and added back during assembling

# Version 0.1.0 / 0.1.1
    
- Started implementation of the library using python 3.10 as the base
- Supporting basic operations like function inlining, and simple data manipulations
- Added a framework for runtime code optimization on bytecode-level using python annotations for hinting certain stuff
- Added experimental support for python 3.11, tested with alpha 4
- Added cpython_changes.md to keep track of the relevant changes to cpython for the library 
