from bytecodemanipulation.data.shared.instructions import (
    MacroAssembly,
    MacroPasteAssembly,
    NamespaceAssembly,
    MacroImportAssembly,
)
from bytecodemanipulation.data.v3_10.instructions import (
    CallAssembly,
    ClassDefinitionAssembly,
    ForEachAssembly,
    FunctionDefinitionAssembly,
    if_assembly,
    jump_assembly,
    load_assembly,
    load_const_assembly,
    load_fast_assembly,
    load_global_assembly,
    macro_return_assembly,
    op_assembly,
    pop_element_assembly,
    raise_assembly,
    return_assembly,
    store_assembly,
    store_fast_assembly,
    store_global_assembly,
    while_assembly,
    yield_assembly,
)


MacroAssembly.MacroAssembly.register()
MacroPasteAssembly.MacroPasteAssembly.register()
NamespaceAssembly.NamespaceAssembly.register()
MacroImportAssembly.MacroImportAssembly.register()
