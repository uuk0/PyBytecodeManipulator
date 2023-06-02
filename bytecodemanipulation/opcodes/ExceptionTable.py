import typing


if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction
    from bytecodemanipulation.opcodes.Instruction import Instruction


class ExceptionTable:
    def __init__(self, target: "MutableFunction"):
        self.target = target

        # handler -> instructions handled
        self.table: typing.Dict["Instruction", typing.List["Instruction"]] = {}

    def add_handle(self, handle: "Instruction", span: typing.Iterable["Instruction"]):
        if handle in self.table:
            self.table[handle] += span
        else:
            self.table[handle] = list(span)

    def remove_handle(self, handle: "Instruction", span: typing.Iterable["Instruction"] = None):
        if handle not in self.table:
            return

        if span is None:
            del self.table[handle]
            return

        for e in span:
            if e in self.table[handle]:
                self.table[handle].remove(e)

    def get_handles_for_instructions(self, instr: "Instruction") -> typing.Iterable["Instruction"]:
        for handle, instructions in self.table.items():
            if instr in instructions:
                yield handle

    def get_span_for_handle(self, instr: "Instruction") -> typing.List["Instruction"]:
        return self.table.get(instr, None) or []

