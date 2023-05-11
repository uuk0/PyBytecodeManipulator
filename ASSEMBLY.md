
# Python Assembly

Python Assembly is an Code Format representing python bytecode, with some meta-instructions
for cross-version support.

## .pyasm files

- implementation in bytecodemanipulation.assembler.hook, which is enabled on import of that module
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
  * 'PARTIAL' is a wrapper like functools.partial. If used, each arg expression can be prefixed with '?' for dynamic evaluation, otherwise static evaluation (like the real functools.partial)
  * 'MACRO' calls macro code, meaning inlining; Parameters of the macro NOT prefixed with '!' will be evaluated on each access by the macro
    * also enables the use of code blocks as parameters (by using '{' \<expressions> '}'' as a parameter)

* OP (\<lhs> \<binary operator> \<rhs>) \['->' \<target>]: uses the given operator
  * binary operator might be any of +|-|*|/|//|**|%|&|"|"|^|>>|<<|@|is|!is|in|!in|<|<=|==|!=|>|>=|xor|!xor|:=|isinstance|issubclass|hasattr|getattr

* IF \<expression> \['\\'' \<label name> '\\''] '{' \<body> '}': executes 'body' only if 'expression' is not False; 'label name' is the top, 'label name'+"_END" the end of the IF statement and 'label name'+"_HEAD" the real HEAD, so before the condition check
* WHILE \<expression> \['\\'' \<label name> '\\''] '{' \<body> '}': executes 'body' while 'expression' is not False; 'label name' is the top, 'label name'+"_END" the end of the WHILE statement and 'label name'+"_INNER" the inner HEAD, without condition check
* FOREACH \<variable> {',' \<variable>} 'IN' \<iterable> {(',' | '\*') \<iterable>}: iterates over the given iterables, using itertools.product on items chained by '*'
* JUMP \<label name> \[(IF \<condition access>) | ('(' \<expression> | \<op expression> ')')] : jumps to the label named 'label name'; if a condition is provided, jumps only if it evals to True

* CLASS \<name> '\<' \<exposed namespace> '\>' \['(' \<parents> ')'] \['->' \<target>] '{' \<body> '}': creates a class; namespace for 'body' is extended by class name!
* DEF \[\<func name>] \['<' \['!'] \<bound variables\> '>'] '(' \<signature> ')' \['->' \<target>] '{' \<body> '}': creates a method named 'func name' (lambda-like if not provided), capturing the outer locals in 'bound variables' (or none)
  using the args stored in 'signature', and optionally storing the result at 'target' (if not provided, at 'func name' if provided else TOS). 'body' is the code itself

* PYTHON '{' \<code> '}': puts the python code in place; '{' and '}' is allowed in code, but the last not matched and not escaped '}' will be used at end of code by the Lexer; WARNING: f-strings are currently NOT supported as they require
  some special handling at the lexer.

* 'MACRO' \['ASSEMBLY'] \<name> \['(' \<param> \[{',' \<param>}] ')'] \['->' \<data type>]  '{' \<assembly code> '}', where param is \['!'] \['MACRO_'] \<name> \[' ' \<data type>] defines a macro in an assembly file, which can be used from outside
  * Call it by using 'CALL MACRO' with the name being the namespace
  * Parameters can be accessed via the '&' prefix
  * use MACRO_RETURN to return from the macro (if it is not at the end of the scope)
  * Parameters may start with 'MACRO_' to make them unique in the target function; otherwise, names are shared
  * WARNING:  N E V E R  call a macro in itself (directly or indirectly). As you might expect, that cannot possibly work, and will most likely crash the compiler
  * Data Types:
    * CODE_BLOCK (a code block in {})
    * VARIABLE_ARG\[...] (a dynamic count (including 0) of the specific type; if no type should be specified, omit the \[])
    * VARIABLE (a variable reference, similar to C#'s 'out' keyword; can be used as a store target than; requires special inputs to work (currently only local, global or cell variables are allowed, in the future more might work))
  * Macro names can be overloaded
  * Comes with an extra instruction, which should only be used in macros:
* MACRO_PASTE \<macro param name> \['->' \<target>]: pastes the code for a macro-parameter, and optionally pushes the result into the target; Can be used to define special exchangeable sections in code (it is intended to be used with code blocks as parameters)
* MACRO_IMPORT \<module name with '.'> \['->' \['.'\] \<namespace with '.'>]: imports the global scope of another module into this scope. If '->' is used, it defines where to put the scope. If it starts with '.', it is relative to the current position, otherwise global.
  * WARNING: the other module must be imported first (TODO: import it manually here!)

* 'NAMESPACE' \[\{\<namespace parts> ':'}] \<main name> '{' \<code> '}': Namespace (internal only, not compiled into bytecode)

* 'RAISE' \[\<source>]: raises the exception at TOS or source 

* ASSERT \<expression> \[\<message>]: asserts that 'expression' evaluates to True, if not, evaluates 'message' or uses the default message and raises an AssertionError

## Python-Pure Instructions (correspond to single opcodes with optional magic)

* LOAD_GLOBAL \<name or index> \['->' \<target>]: pushes the global variable on the stack or stores it at 'target'
* STORE_GLOBAL \<name or index> \[(\<expression>)]: stores TOS or value of 'expression' in the global variable
* LOAD_FAST \<name or index> \['->' \<target>]: pushes the local variable on the stack or stores it at 'target'
* STORE_FAST \<name or index> \[(\<expression>)]: stores TOS or value of 'expression' in the local variable
* LOAD_CONST \<value> | @\<const global source> \['->' \<target>]: loads the constant onto TOS or into 'target'
* POP \[\<count = 1>]: Pops 'count' elements from the stack and discards them
* RETURN \[\<expression>]: Returns the value from TOS or from 'expression'
* YIELD \[*] \[\<expression>] \['->' \<target>]: Yields the value from TOS or from 'expression'; Writes the result into 'target', default is discard; * means 'yield from'
* RAW \<opcode> \[\<arg>]

## Python opcodes not having a corresponding assembly instruction

* CALL_FUNCTION and related: automatically accessed via CALL
* JUMPS: JUMP instruction with label (currently no offset define-able)

## Expressions

Expressions can be added as certain parameters to instructions to use instead of TOS

- Access Expressions:
  - @\<global name>: global variable
  - @!\<global name>: static global variable
  - $\<local name>: local variable
  - §\<name>: access a variable from an outer scope
  - &\<name>: access to a macro parameter
  - %\[\<n>]: top of stack, or the n-th item from TOS
  - \<access>\[\<index or expression>]: value by \[] operator
  - \<access>(\<... args>): call to the attribute; not allowed in CALL opcode source and STORE opcode source
  - '\' for discarding the result of an expression (only when STORING)
- OP instruction, where everything except the 'OP' name is in a single bracket, e.g. "OP ($a + $b)"
- A string literal with " as quotes, and \\" for escaping
- A signed integer or floating-point number
- \<expression>.\<name>: access an attribute of the expression
- \<expression>.(\<expression>): accesses the attribute by an dynamic name


# TODOs
- list / tuple / set / map construction (currently only via std)
  - CREATE \<type> '(' {\<expr>} ')' \['->' \<target>] where type can be list, tuple, set and dict
  - COMPREHENSION \<type> \['\<' \<capture locals> '>'] \<source> '{' \<code> '}' where type can be list, tuple, set, dict, generator and async generator; YIELD statements for emitting to the outside
- can we use offsets as labels in JUMP's? (offsets in assembly instruction and bytecode instructions?)
- FOREACH \['ASYNC'] \['PARALLEL']
- LABEL part for WHILE, FOREACH, FORRANGE and IF (jump to end of if or top if wanted)
- make it IF ... {ELSEIF ...} \[ELSE ...] (single assembly meta instruction)
- IMPORT \<item> \[\<item>] where 'item' is \<package> \['/' \<sub module>] \['->' \<target=sub module name OR package name>]
- TRY '{' \<code> '}' {EXCEPT \['\\'' \<label name> '\\''] \['->' \<exception target>] ('{' \<handle> '}')} \[FINALLY '{' \<code block> '}'] | \<label name>
- CONVERT \<source type> \<target type> \[\<source=TOS>] \['->' \<target=TOS>]
- DEF ASYNC ...
- AWAIT \<expr> \['->' \<target>] and as an expression
- AWAIT '\*' ('(' \<expr> \['->' \<target>] {\<expr> \['->' \<target>]} ')') | ('(' \<expr> {\<expr>} ')' \['->' \<target>]) | (\<expr> \['->' \<target>]) (* = asyncio.gather(...))
- WITH '(' \<expr> \['->' \<target>] {\<expr> \['->' \<target>]} ')' '{' \<body> '}' with special handling for jumps (trigger exit or disable exit)
- CALL INLINE
- CALL MACRO for normal functions (implicit made macros with static parameters), and CALL for macros (implicit made local function)
- More Macro Arg Types:
  - new data type: KEYWORD:'...' where ... is the keyword name to be required (and \' is the escaping for ')
  - new data type: OPTIONAL\<...> where ... is another data type
  - new data type: UNION\<...> where ... is a list of data types, separated by ','
  - new data type: LIST\['\<' \<data type> '>'] where data type is the inner type
  - new data type: CONSTANT\['\<' \<type name> '>']
  - new data type: LABEL exposing a label to the macro, which can be used in places were normal labels can be used (handed over only by name)
  - new specialization for the & macro expansion system: index operator on result where parameter is list will access that item in the list
  - new special case for len(...) on & macro parameter where list: returns len of parameter list
  - storing a list parameter in a local variable will create a list creation code
  - new assembly instruction ASSERT_STATIC (\<condition>) which asserts an expression statically, in this case at instantiation time
  - maybe also the possibility to define code for emitting assembly instructions
    - this could be done by a new instruction called EMIT_INSTRUCTION
  - special annotation for return value target parameter ('->' \<target>), with possibility for multiple targets
  - allow macro parameters to be used in places where identifiers would be used (e.g. variable names, function names, class names, ...)
    - compare against static parameter value at emit time
- CLASS STRUCT ... '\<' \<attr name> {',' \<attr name>} '>' '{' ... '}' to declare a class with \_\_slots__ (and maybe compile-time checks that no other attributes are set on 'self' attributes on functions?)
- CLASS STRUCT IMMUTABLE (for namedtuple stuff)
- CLASS ABSTRACT ... for abstract classes, which includes the abc.ABC baseclass
- DEF ABSTRACT ... for defining abstract methods (no body to declare!)
- ATTR_TYPEDEF \<attr name> \<type definition> in class bodies
- VAR_TYPEDEF \<variable name> \<type definition> everywhere to hint types
- ..._TYPEDEF_STRICT for enforcing types

- make the system more abstract preparing for python 3.11 (CACHE entries, redesigned CALL pattern, ...)

- create abstract classes for the assembly instructions, and force implement them in the versions
  - parsing itself should be in the abstract base, only code emitting in the implementation
- refactor assembly related classes into more files, it is really clustered in only a handful of files

## PyASM

- a syntax highlighter plugin
- maybe make the module parsing (optional) async?
