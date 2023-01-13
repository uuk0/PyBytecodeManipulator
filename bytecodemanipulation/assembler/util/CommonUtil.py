import abc


class AbstractCursorStateItem(abc.ABC):
    def __init__(self):
        self.cursor = 0
        self.cursor_stack = []

    def save(self):
        self.cursor_stack.append(self.cursor)

    def rollback(self):
        self.cursor = self.cursor_stack.pop(-1)

    def discard_save(self):
        self.cursor_stack.pop(-1)
