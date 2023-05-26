

# Call Conventions

## Simple Call

```python
a = b(10, x)
```

will be compiled into:

```
LOAD_FAST b     # method
LOAD_CONST 10   # args (in real order)
LOAD_FAST x
CALL 2          # arg count
STORE_FAST a    # result on stack
```

## Kwarg Call

```python
a = b(10, x=c)
```

will be compiled into:

```
LOAD_FAST b         # method
LOAD_CONST 10       # normal arg
LOAD_FAST c         # kw arg value
LOAD_CONST ("x",)   # kw name list
CALL_FUNCTION_KW 2  # special call opcode with total arg count
STORE_FAST a
```

## \* / \*\* Call

```python
a = b(10, *x, a=10, **y)
```

will be compiled into:

```
LOAD_FAST b              # method name
LOAD_CONST 10            # normal parameter
BUILD_LIST 1             # add normal parameters to list    
LOAD_FAST x              # parameter with *
LIST_EXTEND 1            # extend the list with the new parameter
LIST_TO_TUPLE            # transform to tuple

LOAD_CONST 'a'           # load kw arg key
LOAD_CONST 10            # load the kw arg value
BUILD_MAP 1              # create the kwarg dict
LOAD_NAME y              # load the ** map
DICT_MERGE               # merge the two dicts

CALL_FUNCTION_EX 1       # call the function
STORE_FAST a             # store result
```

# Function Definition

```python
def x(b, *c, )
```
