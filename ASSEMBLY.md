
# Python Assembly

Python Assembly is an Code Format representing python bytecode, with some meta-instructions
for cross-version support.

## .pyasm files

- implementation in bytecodemanipulation.assembler.hook, which is enabled on import
- hooks into the import system with lowest priority so that when a ModuleNotFoundException would be thrown,
  we can look into .pyasm files instead
- will be parsed as normal "inline" assembly, local space is the module scope
- the assembly code will be invoked in a (lambda) method, so you can use "RETURN" at module exit to early exit
- this method gets a single argument called "$module$" (which you cannot access), which defines the scope
- LOAD_FAST, STORE_FAST and DELETE_FAST will be transformed to accessing that parameter instead of the local space

## Meta Instructions (dynamically decide what to use)

* LABEL \<name>: an bytecode label, can be used for jumps (use bytecodemanipulation.assembler.target.label(\<name>) when trying to jump to a instruction not in ASM, but in pure python)

* LOAD \<expression> \['->' \<target>]: Pushes the global or local variable to the stack
* STORE \<expression> \['(' \<expression> ')']: stores TOS or value of 'expression' in the local or global variable
* CALL \['PARTIAL' | 'MACRO'] \<call target> '(' \<args> ')' \['-> '\<target>]: invokes the target found at 'call target' with the given 'args'
  (like python, but with access expressions for values and constant identifiers for keys), and stores it at TOS or 'target';
  'PARTIAL' is a wrapper like functools.partial. If used, each arg expression can be prefixed with '?' for dynamic evaluation, otherwise static evaluation (like the real functools.partial)
* OP (\<lhs> \<binary operator> \<rhs>) \['->' \<target>]: uses the given operator
  * binary operator might be any of +|-|*|/|//|**|%|&|"|"|^|>>|<<|@|is|!is|in|!in|<|<=|==|!=|>|>=|xor|!xor|:=|isinstance|issubclass|hasattr|getattr
* IF \<expression> \['\\'' \<label name> '\\''] '{' \<body> '}': executes 'body' only if 'expression' is not False; 'label name' is the top, 'label name'+"_END" the end of the IF statement and 'label name'+"_HEAD" the real HEAD, so before the condition check
* WHILE \<expression> \['\\'' \<label name> '\\''] '{' \<body> '}': executes 'body' while 'expression' is not False; 'label name' is the top, 'label name'+"_END" the end of the WHILE statement and 'label name'+"_INNER" the inner HEAD, without condition check
* JUMP \<label name> \[(IF \<condition access>) | ('(' \<expression> | \<op expression> ')')] : jumps to the label named 'label name'; if a condition is provided, jumps only if it evals to True
* DEF \[\<func name>] \['<' \['!'] \<bound variables\> '>'] '(' \<signature> ')' \['->' \<target>] '{' \<body> '}': creates a method named 'func name' (lambda-like if not provided), capturing the outer locals in 'bound variables' (or none)
  using the args stored in 'signature', and optionally storing the result at 'target' (if not provided, at 'func name' if provided else TOS). 'body' is the code itself
* PYTHON '{' \<code> '}': puts the python code in place; '{' and '}' is allowed in code, but the last not matched and not escaped '}' will be used at end of code by the Lexer; WARNING: f-strings are currently NOT supported as they require
  some special handling at the lexer.
* 'MACRO' \<name> \['(' \<param> \[{',' \<param>}] ')'] '{' \<assembly code> '}', where param is \<name> \[\<data type>] defines a macro in an assembly file, which can be used from outside
  * Call it by using 'CALL MACRO' with the name being the namespace
  * Parameters can be accessed via the '§' prefix
  * use MACRO_RETURN to return from the macro (if it is not at the end of the scope)
  * Parameters may start with 'MACRO_' to make them unique in the target function; otherwise, names are shared
  * WARNING:  N E V E R  call a macro in itself (directly or indirectly). As you might expect, that cannot possibly work, and will most likely crash the compiler
* 'MACRO_RETURN' \[\<return expression>\]: returns a value from a macro
* 'NAMESPACE' \[\{\<namespace> ':'}] \<name> '{' \<code> '}': Namespace (internal only, not compiled into bytecode)

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
  - $\<name>: access an variable from an outer scope, or a macro parameter
  - %: top of stack (in most cases the default when not provided)
  - \<access>\[\<index or expression>]: value by \[] operator
- OP instruction, where everything except the 'OP' name is in a single bracket, e.g. "OP ($a + $b)"
- A string literal with " as quotes, and \\" for escaping
- A signed integer
- \<expression>.\<name>: access an attribute of the expression
- \<expression>.(\<expression>): accesses the attribute by an dynamic name


# TODOs
- float, list / tuple / set / map construction
  - CREATE \<type> '(' {\<expr>} ')' \['->' \<target>] where type can be list, tuple, set and dict
  - COMPREHENSION \<type> \['\<' \<capture locals> '>'] \<source> '{' \<code> '}' where type can be list, tuple, set, dict, generator and async generator; YIELD statements for emitting to the outside
- can we use offsets as labels in JUMP's?
- add singleton operators for OP
- FOREACH ['async'] (\<expression> \['->' \<target>]) | ('(' \<expression> ')' \['->' \<target>] {\['&'] '(' \<expression> ')' \['->' \<target>]}) '{' \<code> '}' iterates over all iterator expressions; when prefixed with '&', it will be zip()-ed with the previous iterator in the expression list
- FORRANGE '(' \[\<start> ','] \<stop> \[',' \<step>] ')' \['->' \<target>] {'(' '(' \[\<start> ','] \<stop> \[ ',' \<step>] ')' \['->' \<target>] ')'} '{' \<code> '}' iterates over the ranges one after each other ('&' like above makes no sense here)
- CALL as expression (most likely with \<target>(...))
- LABEL part for WHILE, FOREACH, FORRANGE and IF (jump to end of if or top if wanted)
- make it IF ... {ELSEIF ...} \[ELSE ...] (single assembly meta instruction)
- CLASS \<name> \['(' \<parents> ')'] \['->' \<target>] '{' \<body> '}'
- IMPORT \<item> \[\<item>] where 'item' is \<package> \['/' \<sub module>] \['->' \<target=sub module name OR package name>]
- DEF TEMPLATE ... exports an template function (auto-inlined), where args might be prefixed with '?' for copying the bytecode instead of the value,
  target must be '<name>' (and must be provided), exposing it as a static-resolved thing; Invoked via CALL '<name' ...
- TRY '{' \<code> '}' CATCH \['\\'' \<label name> '\\''] \['->' \<exception target>] ('{' \<handle> '}') | \<label name>
- CONVERT \<source type> \<target type> \[\<source=TOS>] \['->' \<target=TOS>]
- DEF ASYNC ...
- AWAIT \<expr> \['->' \<target>] and as an expression
- AWAIT '*' ('(' \<expr> \['->' \<target>] {\<expr> \['->' \<target>]} ')') | ('(' \<expr> {\<expr>} ')' \['->' \<target>]) | (\<expr> \['->' \<target>]) (* = asyncio.gather(...))
- WITH '(' \<expr> \['->' \<target>] {\<expr> \['->' \<target>]} ')' '{' \<body> '}' with special handling for jumps (trigger exit or disable exit)
- RAW \<opcode> \[\<arg> | \<arg value>]
- PROPOSE \<type> \<value>
- CALL INLINE
- ITERATOR_OP (stream util)

## PyASM

- a syntax highlighter plugin
