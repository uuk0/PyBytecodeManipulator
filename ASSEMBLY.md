
# Python Assembly

Python Assembly is an Code Format representing python bytecode, with some meta-instructions
for cross-version support.

## Meta Instructions (dynamically decide what to use)

* LABEL \<name>: an bytecode label, can be used for jumps (use bytecodemanipulation.assembler.target.label(\<name>) when trying to jump to a instruction not in ASM, but in pure python)

* LOAD \<expression> \['->' \<target>]: Pushes the global or local variable to the stack
* STORE \<expression> \['(' \<expression> ')']: stores TOS or value of 'expression' in the local or global variable
* CALL \<call target> '(' \<args> ')' \['-> '\<target>]: invokes the target found at 'call target' with the given 'args' (like python, but with access expressions for values and constant identifiers for keys), and stores it at TOS or 'target'
* OP (\<lhs> \<binary operator> \<rhs>) \['->' \<target>]: uses the given operator
  * binary operator might be any of +|-|*|/|//|**|%|&|"|"|^|>>|<<|@|is|nis|<|<=|==|!=|>|>=|xor|xnor
* IF \<expression> '{' \<body> '}': executes 'body' only if 'expression' is not False
* WHILE \<expression> '{' \<body> '}': executes 'body' while 'expression' is not False
* JUMP \<label name> \[(IF \<condition access>) | ('(' \<expression> | \<op expression> ')')] : jumps to the label named 'label name'; if a condition is provided, jumps only if it evals to True
* DEF \[\<func name>] \['<' \['!'] \<bound variables\> '>'] '(' \<signature> ')' \['->' \<target>] '{' \<body> '}': creates a method named 'func name' (lambda-like if not provided), capturing the outer locals in 'bound variables' (or none)
  using the args stored in 'signature', and optionally storing the result at 'target' (if not provided, at 'func name' if provided else TOS). 'body' is the code itself
* PYTHON '{' \<code> '}': puts the python code in place; '{' and '}' is allowed in code, but the last not matched and not escaped '}' will be used at end of code by the Lexer; WARNING: f-strings are currently NOT supported as they require
  some special handling at the lexer.

## Python-Pure Instructions (correspond to single opcodes with optional magic)

* LOAD_GLOBAL \<name or index> \['->' \<target>]: pushes the global variable on the stack or stores it at 'target'
* STORE_GLOBAL \<name or index> \[(\<expression>)]: stores TOS or value of 'expression' in the global variable
* LOAD_FAST \<name or index> \['->' \<target>]: pushes the local variable on the stack or stores it at 'target'
* STORE_FAST \<name or index> \[(\<expression>)]: stores TOS or value of 'expression' in the local variable
* LOAD_CONST \<value> | @\<const global source> \['->' \<target>]: loads the constant onto TOS or into 'target'
* POP \[\<count = 1>]: Pops 'count' elements from the stack and discards them
* RETURN \[\<expression>]: Returns the value from TOS or from 'expression'
* YIELD \[*] \[\<expression>] \['->' \<target>]: Yields the value from TOS or from 'expression'; Writes the result into 'target', default is discard; * means 'yield from'

## Python opcodes not having a corresponding assembly instruction

* CALL_FUNCTION and related: automatically accessed via CALL
* JUMPS: JUMP instruction with label (currently no offset define-able)

## Expressions

Expressions can be added as certain parameters to instructions to use instead of TOS

- Access Expressions:
  - @\<global name>: global variable
  - @!\<global name>: static global variable
  - $\<local name>: local variable
  - %: top of stack (in most cases the default when not provided)
  - \<access>[\<index or expression>]: value by [] operator
- OP instruction, where everything except the 'OP' name is in a single bracket, e.g. "OP ($a + $b)"
- A string literal with " as quotes, and \\" for escaping
- A signed integer
- \<expression>.\<name>: access an attribute of the expression


# TODOs
- float, list / tuple / set / map construction
- can we use offsets as labels in JUMP's?
- add singleton operators for OP
- add ':=' binary operator
- CALL PARTIAL (...) wraps the target in functools.partial; expressions can be prefixed with '?' for dynamic resolving
- FOREACH (\<expression> ['->' \<target>]) | ('(' \<expression> ')' ['->' \<target>] {['&'] '(' \<expression> ')' ['->' \<target>]}) iterates over all iterator expressions; when prefixed with '&', it will be zip()-ed with the previous iterator in the expression list
- FORRANGE '(' [\<start>, ]\<stop>[, \<step>] ')' ['->' \<target>] {'(' '(' [\<start>, ]\<stop>[, \<step>] ')' ['->' \<target>] ')'} iterates over the ranges one after each other
- CALL as expression (most likely with \<target>(...)
