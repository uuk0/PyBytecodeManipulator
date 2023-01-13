
# Python Assembly

Python Assembly is an Code Format representing python bytecode, with some meta-instructions
for cross-version support.

## Meta Instructions

* LOAD @\<global name or index> | $\<local name or index>: Pushes the global or local variable to the stack
* STORE @\<global name or index> | $\<local name or index> [(\<expression>)]: stores TOS or value of 'expression' in the local or global variable

## Python-Pure Instructions

* LOAD_GLOBAL \<name or index>: pushes the global variable on the stack
* STORE_GLOBAL \<name or index> [(\<expression>)]: stores TOS or value of 'expression' in the global variable
* LOAD_FAST \<name or index>: pushes the local variable on the stack
* STORE_FAST \<name or index> [(\<expression>)]: stores TOS or value of 'expression' in the local variable
* LOAD_CONST \<value>
* POP [<count = 1>]: Pops 'count' elements from the stack and discards them

## Expressions

Expressions can be added as certain parameters to instructions to use instead of TOS

- Access Expressions:
  - @\<global name>: global variable
  - $\<local name>: local variable
  - %: top of stack (in most cases the default when not provided)
  - \<access>[\<index or expression>]: value by [] operator
- OP instruction
- A string literal with " as quotes, and \\" for escaping
