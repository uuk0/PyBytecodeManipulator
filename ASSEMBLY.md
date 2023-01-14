
# Python Assembly

Python Assembly is an Code Format representing python bytecode, with some meta-instructions
for cross-version support.

## Meta Instructions (dynamically decide what to use)

* LOAD \<expression> [-> \<target>]: Pushes the global or local variable to the stack
* STORE \<expression> ['(' \<expression> ')']: stores TOS or value of 'expression' in the local or global variable
* CALL \<call target> '(' \<args> ')' [-> \<target>]: invokes the target found at 'call target' with the given 'args' (like python, but with access expressions for values and constant identifiers for keys), and stores it at TOS or 'target'
* OP (\<lhs> \<binary operator> \<rhs>) [-> \<target>]: uses the given operator
  * binary operator might be any of +|-|*|/|//|**|%|&|"|"|^|>>|<<|@

## Python-Pure Instructions (correspond to single opcodes with optional magic)

* LOAD_GLOBAL \<name or index> [-> \<target>]: pushes the global variable on the stack or stores it at 'target'
* STORE_GLOBAL \<name or index> [(\<expression>)]: stores TOS or value of 'expression' in the global variable
* LOAD_FAST \<name or index> [-> \<target>]: pushes the local variable on the stack or stores it at 'target'
* STORE_FAST \<name or index> [(\<expression>)]: stores TOS or value of 'expression' in the local variable
* LOAD_CONST \<value> | @\<const global source> [-> \<target>]: loads the constant onto TOS or into 'target'
* POP [<count = 1>]: Pops 'count' elements from the stack and discards them

## Python opcodes not having a corresponding assembly instruction

* CALL_FUNCTION and related: automatically accessed via CALL

## Expressions

Expressions can be added as certain parameters to instructions to use instead of TOS

- Access Expressions:
  - @\<global name>: global variable
  - $\<local name>: local variable
  - %: top of stack (in most cases the default when not provided)
  - \<access>[\<index or expression>]: value by [] operator
- OP instruction
- A string literal with " as quotes, and \\" for escaping
- A signed integer
- \<expression>.\<name>: access an attribute of the expression

TODO: float, list / tuple / set / map construction
