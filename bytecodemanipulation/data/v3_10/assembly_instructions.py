from bytecodemanipulation.data.shared.instructions import (
    MacroAssembly,
    MacroPasteAssembly,
    NamespaceAssembly,
    MacroImportAssembly,
    LoadAssembly,
)
from bytecodemanipulation.data.v3_10.instructions import (
    CallAssembly,
    ClassDefinitionAssembly,
    ForEachAssembly,
    FunctionDefinitionAssembly,
    IfAssembly,
    JumpAssembly,
    LoadConstAssembly,
    LoadFastAssembly,
    LoadGlobalAssembly,
    macro_return_assembly,
    OpAssembly,
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
