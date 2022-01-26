# todo: implement more matchers
import dis
import typing

from bytecodemanipulation.TransformationHelper import BytecodePatchHelper


class AbstractInstructionMatcher:
    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        raise NotImplementedError

    def __and__(self, other):
        if isinstance(other, AndMatcher):
            return AndMatcher(self, *other.matchers)

        return AndMatcher(self, other)

    def __or__(self, other):
        if isinstance(other, OrMatcher):
            return OrMatcher(self, *other.matchers)

        return OrMatcher(self, other)

    def __invert__(self):
        return NotMatcher(self)


class AndMatcher(AbstractInstructionMatcher):
    def __init__(self, *matchers: AbstractInstructionMatcher):
        self.matchers = matchers

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        return all(
            matcher.matches(function, index, match_count) for matcher in self.matchers
        )

    def __and__(self, other):
        if isinstance(other, AndMatcher):
            return AndMatcher(*self.matchers, *other.matchers)
        return AndMatcher(*self.matchers, other)


class OrMatcher(AbstractInstructionMatcher):
    def __init__(self, *matchers: AbstractInstructionMatcher):
        self.matchers = matchers

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        return any(
            matcher.matches(function, index, match_count) for matcher in self.matchers
        )

    def __or__(self, other):
        if isinstance(other, OrMatcher):
            return OrMatcher(*self.matchers, *other.matchers)
        return OrMatcher(*self.matchers, other)


class NotMatcher(AbstractInstructionMatcher):
    def __init__(self, matcher: AbstractInstructionMatcher):
        self.matcher = matcher

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        return not self.matcher.matches(function, index, match_count)

    def __invert__(self):
        return self.matcher


class AnyByInstructionNameMatcher(AbstractInstructionMatcher):
    def __init__(self, opname: str):
        self.opname = opname

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        return function.instruction_listing[index].opname == self.opname


class IndexBasedMatcher(AbstractInstructionMatcher):
    def __init__(
        self,
        start: int,
        end: int = None,
        sub_matcher: AbstractInstructionMatcher = None,
    ):
        self.start = start
        self.end = end
        self.sub_matcher = sub_matcher

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        if index < self.start:
            return False
        if self.end is not None and index > self.end:
            return False
        if self.sub_matcher:
            return self.sub_matcher.matches(function, index, match_count)

        return True


class SurroundingBasedMatcher(AbstractInstructionMatcher):
    def __init__(self, this_matcher: AbstractInstructionMatcher = None):
        self.this_matcher = this_matcher
        self.size = 0, 0
        self.matchers: typing.Tuple[
            typing.List[AbstractInstructionMatcher],
            typing.List[AbstractInstructionMatcher],
        ] = ([], [])

    def set_offset_matcher(self, offset: int, matcher: AbstractInstructionMatcher):
        if offset < 0:
            self.size = min(offset, self.size[0]), self.size[1]
            if len(self.matchers[0]) < abs(offset):
                self.matchers[0] += [None] * (abs(offset) - len(self.matchers[0]))
            self.matchers[0][offset] = matcher
        else:
            self.size = self.size[0], max(offset, self.size[1])
            if len(self.matchers[1]) < offset:
                self.matchers[0] += [None] * (offset - len(self.matchers[0]))
            self.matchers[1][offset - 1] = matcher

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        if (
            index + self.size[0] < 0
            or index + self.size[1] >= len(function.patcher.code.co_code) // 2
        ):
            return False

        for i in range(len(self.matchers[0])):
            dx = -(len(self.matchers[0]) - i)
            if not self.matchers[0][i].matches(function, index + dx, match_count):
                return False

        for i in range(len(self.matchers[1])):
            if not self.matchers[0][i].matches(function, index + i + 1, match_count):
                return False

        if self.this_matcher is not None:
            return self.this_matcher.matches(function, index, match_count)

        return True


class LoadConstantValueMatcher(AbstractInstructionMatcher):
    def __init__(self, value):
        self.value = value

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        instr = function.instruction_listing[index]
        return instr.opname == "LOAD_CONST" and instr.argval == self.value


class LoadGlobalMatcher(AbstractInstructionMatcher):
    def __init__(self, global_name: str):
        self.global_name = global_name

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        instr = function.instruction_listing[index]
        return instr.opname == "LOAD_GLOBAL" and instr.argval == self.global_name


class CounterMatcher(AbstractInstructionMatcher):
    def __init__(self, count_start: int, count_end: int = None):
        self.count_start = count_start
        self.count_end = count_end or count_start

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        return self.count_start <= match_count <= self.count_end


class MetaArgMatcher(AbstractInstructionMatcher):
    def __init__(self, inner_matcher: typing.Callable[[BytecodePatchHelper, typing.Any], bool]):
        self.inner_matcher = inner_matcher

    def matches(self, function: BytecodePatchHelper, index: int, match_count: int) -> bool:
        value = function.instruction_listing[index].argval
        return self.inner_matcher(function, value)
