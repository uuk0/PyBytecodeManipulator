
# Version 0.3.5
- std:comprehension:list is now using internally a generator wrapped in a list() call
- added std:comprehension:generator, :set, :tuple and :map
- fixed YIELD in function definition blocks
- fix macro-in-macro calls
- removed std:print as it can be implemented using ~print(...) in the same way
- rewritten how exceptions are emitted, making it possible to generate good trace backs without
  all the internal stuff; added more exceptions in the process
- fixed some opcode stack effects
- more test coverage
- AttributeAccess itself is no longer evaluated statically, as it may lead to unwanted side effects
- added std:stream:reduce with start value and std:stream:grouped
- fixed issue with the lexer when parsing negativ integers

# Version 0.3.4
- improved error messages for assemblies
- label names may now contain ':', and be based on macro-expanded names,
  used when labels are generated for e.g. for loops, using now the interfix ':' 
- CODE_BLOCK data type can now expose 'parameters' to the caller, so the implementation detail is hidden.
  Use the data type CODE_BLOCK\[\<parameter count>] together with MACRO_PASTE \<var> \[\<expressions...>]
  and \[\<local var names>] {\<code>}
- added constants ~PY_VERSION and ~BCM_VERSION
- IF assembly tries now to evaluate the expression ahead of time, making compile-time decisions if to include code or not
- new operators: tuple, list, set and dict
- fixed some optimiser stuff when statically doing operators
- improved code for capturing outer locals (rewritten as freevars cannot be created)
- made std:comprehension:list working

# Version 0.3.3
- added new virtual opcodes for compare operations
- exception handles are now stored in their own structure
- added andeval operator
- refactored Instruction class, removing the 'owner' function, and removing the 'offset' from the constructor
- fixed access to global statically and attributes statically
- source code location info for instructions should now be encoded correctly
- changed macro local access: by default, macro only, ':' prefix now for outer (e.g. $:outer)
- macro parameters used in MACRO_PASTE are not affected by outer-prefix need; their local accesses
  are automatically bound to outer variables; use the '|' prefix in order to prevent this
- added warning when using locals not already set ahead of time
- more error messages when using slightly wrong syntax (fixing edge cases that would be allowed)
- keyword argument names in function definitions and function calls can now be any identifier-like, including macro expanded names

# Version 0.3.1
- added oreval operator, acting like python's or operator, returning the righthandside if the left hand side is false-like
- added ASSERT_STATIC assembly
- rewritten how the Instruction's are stored in MutableFunction, using now a real graph

# Version 0.2.9
- added RAW assembly instruction
- refactored operator system
- added new operators: and, or, nand, nor, =:, sum, prod, avg, avgi
- removed operator: getattr
- rewritten operator: xor, xnor (now using \_\_bool__ instead of \_\_eq__)
- classes do no longer have their own namespace, if you still want a namespace, you may use '\<' \<namespace name> '\>' after the class name
- functions and classes support now macro expansions for their names
- macro expanded names can now be correctly compared, hashed, etc.
- setting ASSERT_TYPE_CASTS in builtin_spec to True will now enforce types in specialization, not like a no-op like default
- partial support for inlining function calls
- added ASSERT \<expression> \[\<message>] instruction

# Version 0.2.8
- added FOREACH loops with automatically zip() when multiple iterable are given
- changed the macro prefix from § to &
- using &\<name> in places for identifiers is now allowed in some places
- added std:comprehension:list to feel like python list comprehension
- refactored assembly part of the project

# Version 0.2.4
- added more assembly code
- fixed some issues with the bytecode part
- added some more specializations
- added error locations to assembly code

0.2.3: never released

# Version 0.2.2
- added assembly system, including macros

# Version 0.2.1
- added a few more opcodes
- fixed potential issue when the system does not detect children of classes correctly, when only the class is annotated
- added specialization system; functions can now declare 'specializations', which are applied at optimisation time
- started writing an assembly parser; In the future, this will be used for providing inline assembly code

# Version 0.2.0
- rewritten the whole system
- now a lot more stable, and allows better bytecode manipulation at low level

# Version 0.1.- [never released]
- made some instruction configs .json config able
- emulator will crash now with a good exception message when a jump goes out of bounds
- @name_is_static() annotation will now forward the matcher argument correctly
- some of the not documented optimization annotations were changed
- fixed issue with name_is_static() not correctly resolving the name
- fixed issues with some source instr following failing
- improved cases for optimisation

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
