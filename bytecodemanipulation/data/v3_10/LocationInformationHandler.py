import typing

from bytecodemanipulation.opcodes.AbstractOpcodeTransformerStage import AbstractOpcodeTransformerStage


if typing.TYPE_CHECKING:
    from bytecodemanipulation.MutableFunction import MutableFunction
    from bytecodemanipulation.opcodes.CodeObjectBuilder import CodeObjectBuilder


class LocationInformationDecoder(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", metadata: typing.Any) -> typing.Any:
        pass


class LocationInformationEncoder(AbstractOpcodeTransformerStage):
    @classmethod
    def apply(cls, function: "MutableFunction", builder: "CodeObjectBuilder"):
        items = []

        prev_line = function.code_object.co_firstlineno
        count_since_previous = 0

        for instr in builder.temporary_instructions:
            count_since_previous += 1

            if instr.source_location is None:
                offset = 0
            elif instr.source_location[0] == prev_line:
                continue
            else:
                offset = instr.source_location[0] - prev_line

            if offset > 127:
                offset = 127
                # todo: maybe insert NOP?

            if offset < 0:
                print("WARN", instr, offset)
                print(instr.source_location, prev_line)
                offset = 0

            items.append(count_since_previous)
            items.append(offset)
            count_since_previous = 0

        builder.line_info_table = bytes(items)
        builder.first_line_number = function.code_object.co_firstlineno

