from bytecodemanipulation.data.shared.instructions import (
    MacroAssembly,
    MacroPasteAssembly,
    NamespaceAssembly,
    MacroImportAssembly,
    LoadAssembly,
    StoreAssembly,
    MacroReturnAssembly,
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
    OpAssembly,
    PopElementAssembly,
    RaiseAssembly,
    ReturnAssembly,
    store_fast_assembly,
    store_global_assembly,
    while_assembly,
    yield_assembly,
)


MacroAssembly.MacroAssembly.register()
MacroPasteAssembly.MacroPasteAssembly.register()
NamespaceAssembly.NamespaceAssembly.register()
MacroImportAssembly.MacroImportAssembly.register()
