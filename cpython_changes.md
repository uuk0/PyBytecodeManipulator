
This is a list of relevant changes to the internal python API 
we rely on


# Python 3.12

First commit: https://github.com/python/cpython/commit/e851177536b44ebc616ddbe51aebcd1f30857f34

## Python 3.12a0

Core (Bytecode):
- https://github.com/python/cpython/issues/93382: Speed up the PyCode_GetCode() function which also improves accessing the co_code attribute in Python.
- https://github.com/python/cpython/issues/93223: When a bytecode instruction jumps to an unconditional jump instruction, the first instruction can often be optimized to target the unconditional jump’s target directly. For tracing reasons, this would previously only occur if both instructions have the same line number. This also now occurs if the unconditional jump is artificial, i.e., if it has no associated line number.
- https://github.com/python/cpython/issues/93143: Avoid NULL checks for uninitialized local variables by determining at compile time which variables must be initialized.
- https://github.com/python/cpython/issues/93061: Backward jumps after async for loops are no longer given dubious line numbers.
- https://github.com/python/cpython/issues/89914: The operand of the YIELD_VALUE instruction is set to the stack depth. This is done to help frame handling on yield and may assist debuggers.
- https://github.com/python/cpython/issues/90690: The PRECALL instruction has been removed. It offered only a small advantage for specialization and is not needed in the vast majority of cases.
- https://github.com/python/cpython/issues/92777: Specialize LOAD_METHOD for objects with lazy dictionaries. Patch by Ken Jin.
- https://github.com/python/cpython/issues/92619: Make the compiler duplicate an exit block only if none of its instructions have a lineno (previously only the first instruction in the block was checked, leading to unnecessarily duplicated blocks).


# Python 3.11

## Python 3.11a5 (not complete)

- https://bugs.python.org/issue46409: Added new RETURN_GENERATOR(75) bytecode to make generators.
  Simplifies calling Python functions in the VM, as they no longer any need to special case generator functions.
- https://bugs.python.org/issue46409: Added JUMP_NO_INTERRUPT bytecode that acts like JUMP_ABSOLUTE, but does not check for interrupts.
- https://bugs.python.org/issue46161: Fix the class building error when the arguments are constants and CALL_FUNCTION_EX is used.
- https://bugs.python.org/issue43118: Fix a bug in inspect.signature() that was causing it to fail on some subclasses of classes with a __text_signature__ referencing module globals.
- https://bugs.python.org/issue43683: Add ASYNC_GEN_WRAP opcode to wrap the value to be yielded in async generators. Removes the need to special case async generators in the YIELD_VALUE instruction.
- https://bugs.python.org/issue46458: Reorder code emitted by the compiler for a try-except block so that the else block’s code immediately follows the try body (without a jump). This is more optimal for the happy path.

Major

Bytecode change -> implement helper code for simulating that instructions

    https://bugs.python.org/issue46528
    Replace several stack manipulation instructions 
    DUP_TOP, DUP_TOP_TWO, ROT_TWO, ROT_THREE, ROT_FOUR, and ROT_N
    with new COPY and SWAP instructions.


Change how function calls are done (again)

    https://bugs.python.org/issue46329

    Use two or three bytecodes to implement most calls.
  
    Calls without named arguments are implemented as a sequence of two instructions: 
    PRECALL; CALL.

    Calls with named arguments are implemented as a sequence of three instructions: 
    PRECALL; KW_NAMES; CALL. 

    There are two different PRECALL instructions: 
    PRECALL_FUNTION and PRECALL_METHOD. The latter pairs with LOAD_METHOD.
    
    This partition into pre-call and call allows better specialization, 
    and thus better performance ultimately.
    
    There is no change in semantics.

## Python 3.11a4 [currently build against]

Bytecode related 

- (https://bugs.python.org/issue46314: Remove spurious “call” event when creating a lambda function that was accidentally introduced in 3.11a4)
- https://bugs.python.org/issue45923: Add RESUME opcode. This is a logical no-op. It is emitted by the compiler anywhere a Python function can be entered. It is used by the interpreter to perform tracing and optimizer checks
- https://bugs.python.org/issue46009: Remove the GEN_START opcode
- (https://bugs.python.org/issue46221: PREP_RERAISE_STAR no longer pushes lasti to the stack)
- (https://bugs.python.org/issue46202: Remove POP_EXCEPT_AND_RERAISE and replace it by an equivalent sequence of other opcodes)
- https://bugs.python.org/issue46039: Remove the YIELD_FROM instruction and replace it with the SEND instruction which performs the same operation, but without the loop.
- https://bugs.python.org/issue46031: Add POP_JUMP_IF_NOT_NONE and POP_JUMP_IF_NONE opcodes to speed up conditional jumps.
- https://bugs.python.org/issue44525: Specialize the CALL_FUNCTION instruction for calls to builtin types with a single argument. Speeds up range(x), list(x), and specifically type(obj)

Marking related:
- https://bugs.python.org/issue46342: The @typing.final decorator now sets the \_\_final__ attribute on the decorated object to allow runtime introspection


Major:

    https://bugs.python.org/issue44525
    
    Replace the four call bytecode instructions which one pre-call instruction and two call instructions.
    
    Removes CALL_FUNCTION, CALL_FUNCTION_KW, CALL_METHOD and CALL_METHOD_KW. 
    
    Adds CALL_NO_KW and CALL_KW call instructions, and PRECALL_METHOD prefix for pairing with LOAD_METHOD.

## Python 3.11a3

- (https://bugs.python.org/issue44530: Reverts a change to the code.\_\_new__ audit event from an earlier prerelease)
- https://bugs.python.org/issue45885: Specialized the COMPARE_OP opcode using the PEP 659 machinery
- https://bugs.python.org/issue44525: Adds new COPY_FREE_VARS opcode, to make copying of free variables from function to frame explicit. Helps optimization of calls to Python function
- https://bugs.python.org/issue45829: Specialize BINARY_SUBSCR for classes with a \_\_getitem__ method implemented in Python
- https://bugs.python.org/issue45636: Simplify the implementation of BINARY_OP by indexing into an array of function pointers (rather than switching on the oparg)
- https://bugs.python.org/issue45773: Fix a compiler hang when attempting to optimize certain jump patterns
- https://bugs.python.org/issue45609: Specialized the STORE_SUBSCR opcode using the PEP 659 machinery.

Major

    https://bugs.python.org/issue45636

    Replace all numeric BINARY_* and INPLACE_* instructions with a single BINARY_OP implementation.

    (not implemented in this library)

## Python 3.11a2

Bytecode related
- https://bugs.python.org/issue44525: Specialize simple calls to Python functions (no starargs, keyowrd dict, or closure)
- https://bugs.python.org/issue30570: Fixed a crash in issubclass() from infinite recursion when searching pathological \_\_bases__ tuples
- https://bugs.python.org/issue45340: Object attributes are held in an array instead of a dictionary. An object’s dictionary are created lazily, only when needed. Reduces the memory consumption of a typical Python object by about 30%
- https://bugs.python.org/issue45367: Specialized the BINARY_MULTIPLY opcode to BINARY_MULTIPLY_INT and BINARY_MULTIPLY_FLOAT using the PEP 659 machinery
- https://bugs.python.org/issue44525: Setup initial specialization infrastructure for the CALL_FUNCTION opcode. Implemented initial specializations for C function calls: CALL_FUNCTION_BUILTIN_O for METH_O flag. CALL_FUNCTION_BUILTIN_FAST for METH_FASTCALL flag without keywords. CALL_FUNCTION_LEN for len(o). CALL_FUNCTION_ISINSTANCE for isinstance(o, t)
- https://bugs.python.org/issue44511: Improve the generated bytecode for class and mapping patterns
- https://bugs.python.org/issue45406: Make inspect.getmodule() catch FileNotFoundError raised by :’func:inspect.getabsfile, and return None to indicate that the module could not be determined

Optimiser related:
- https://bugs.python.org/issue42222: Removed deprecated support for float arguments in randrange()

## Python 3.11a1

Bytecode related:
- https://bugs.python.org/issue45056: Compiler now removes trailing unused constants from co_consts
- https://bugs.python.org/issue44945: Specialize the BINARY_ADD instruction using the PEP 659 machinery. Adds five new instructions: BINARY_ADD_ADAPTIVE, BINARY_ADD_FLOAT, BINARY_ADD_INT, BINARY_ADD_UNICODE, BINARY_ADD_UNICODE_INPLACE_FAST
- https://bugs.python.org/issue44900: Add five superinstructions for PEP 659 quickening: LOAD_FAST LOAD_FAST, STORE_FAST LOAD_FAST, LOAD_FAST LOAD_CONST, LOAD_CONST LOAD_FAST, STORE_FAST STORE_FAST
- https://bugs.python.org/issue44889: Initial implementation of adaptive specialization of LOAD_METHOD. The following specialized forms were added: LOAD_METHOD_CACHED, LOAD_METHOD_MODULE, LOAD_METHOD_CLASS
- https://bugs.python.org/issue44826: Initial implementation of adaptive specialization of STORE_ATTR: Three specialized forms of STORE_ATTR are added: STORE_ATTR_SLOT, STORE_ATTR_SPLIT_KEYS, STORE_ATTR_WITH_HINT
- https://bugs.python.org/issue44725: Expose specialization stats in python via _opcode.get_specialization_stats()
- https://bugs.python.org/issue26280: Implement adaptive specialization for BINARY_SUBSCR; Three specialized forms of BINARY_SUBSCR are added: BINARY_SUBSCR_LIST_INT, BINARY_SUBSCR_TUPLE_INT, BINARY_SUBSCR_DICT
- https://bugs.python.org/issue44313: Directly imported objects and modules (through import and from import statements) don’t generate LOAD_METHOD/CALL_METHOD for directly accessed objects on their namespace. They now use the regular LOAD_ATTR/CALL_FUNCTION
- https://bugs.python.org/issue44338: Implement adaptive specialization for LOAD_GLOBAL; Two specialized forms of LOAD_GLOBAL are added: LOAD_GLOBAL_MODULE, LOAD_GLOBAL_BUILTIN
- https://bugs.python.org/issue44337: Initial implementation of adaptive specialization of LOAD_ATTR; Four specialized forms of LOAD_ATTR are added: LOAD_ATTR_SLOT, LOAD_ATTR_SPLIT_KEYS, LOAD_ATTR_WITH_HINT, LOAD_ATTR_MODULE
- https://bugs.python.org/issue43693: A new opcode MAKE_CELL has been added that effectively moves some of the work done on function entry into the compiler and into the eval loop. In addition to creating the required cell objects, the new opcode converts relevant arguments (and other locals) to cell variables on function entry.
- https://bugs.python.org/issue26110: Add CALL_METHOD_KW opcode to speed up method calls with keyword arguments. Idea originated from PyPy. A side effect is executing CALL_METHOD is now branchless in the evaluation loop.
- https://bugs.python.org/issue28307: Compiler now optimizes simple C-style formatting with literal format containing only format codes %s, %r and %a by converting them to f-string expressions.
- https://bugs.python.org/issue43693: Compute cell offsets relative to locals in compiler. Allows the interpreter to treats locals and cells a single array, which is slightly more efficient. Also make the LOAD_CLOSURE opcode an alias for LOAD_FAST. Preserving LOAD_CLOSURE helps keep bytecode a bit more readable.
- https://bugs.python.org/issue17792: More accurate error messages for access of unbound locals or free vars
- https://bugs.python.org/issue33346: Asynchronous comprehensions are now allowed inside comprehensions in asynchronous functions. Outer comprehensions implicitly become asynchronous.


MAJOR

    https://bugs.python.org/issue40222

    “Zero cost” exception handling.

    Uses a lookup table to determine how to handle exceptions.

    Removes SETUP_FINALLY and POP_TOP block instructions, eliminating the runtime overhead of try statements.

    Reduces the size of the frame object by about 60%.



Code-object related:
- https://bugs.python.org/issue43693: PyCodeObject gained co_fastlocalnames and co_fastlocalkinds as the authoritative source of fast locals info. Marshaled code objects have changed accordingly.
