from bytecodemanipulation.OptimiserAnnotations import constant_operation


# math
import math

constant_operation()(math.sin)
constant_operation()(math.cos)
constant_operation()(math.tan)
constant_operation()(math.asin)
constant_operation()(math.acos)
constant_operation()(math.atan)


