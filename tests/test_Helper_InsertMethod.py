import dis
import sys

from unittest import TestCase

from bytecodemanipulation.TransformationHelper import (
    MutableCodeObject,
    BytecodePatchHelper,
    capture_local,
    capture_local_static,
    injected_return,
)


INVOKED = 0


class TestInsertMethod(TestCase):
    def test_insert_method_1(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            return 0

        def test():
            global INVOKED
            INVOKED = True

        helper = BytecodePatchHelper(target)
        helper.insertMethodAt(0, MutableCodeObject(test))
        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        target()
        self.assertTrue(INVOKED)
        INVOKED = False

    def test_insert_method_local_capture_5(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            a = 1
            b = 2
            return a

        def test():
            x = capture_local("a")
            y = capture_local("b")
            global INVOKED
            INVOKED = x + y
            a = 2

        self.assertEqual(target(), 1)

        helper = BytecodePatchHelper(target)
        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(4, MutableCodeObject(test))
        else:
            helper.insertMethodAt(5, MutableCodeObject(test))
        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        self.assertEqual(target(), 1, "local protection unsuccessful")
        self.assertEqual(INVOKED, 3)
        INVOKED = False

    def test_insert_method_local_capture_1(self):
        def target():
            a = 1
            return 0

        def test():
            x = capture_local("a")
            global INVOKED
            INVOKED = x

        helper = BytecodePatchHelper(target)

        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(2, MutableCodeObject(test))
        else:
            helper.insertMethodAt(3, MutableCodeObject(test))

        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        target()
        self.assertEqual(INVOKED, 1)
        INVOKED = False

    def test_insert_method_local_capture_2(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            a = 1
            return a

        def test():
            x = capture_local("a")
            global INVOKED
            INVOKED = x
            x = 2

        helper = BytecodePatchHelper(target)

        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(2, MutableCodeObject(test))
        else:
            helper.insertMethodAt(3, MutableCodeObject(test))

        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        self.assertEqual(target(), 2)
        self.assertEqual(INVOKED, 1)
        INVOKED = False

    def test_insert_method_local_capture_static_2(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            a = 1
            return a

        def test():
            x = capture_local_static("a")
            global INVOKED
            INVOKED = x
            x = 2

        helper = BytecodePatchHelper(target)

        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(2, MutableCodeObject(test))
        else:
            helper.insertMethodAt(3, MutableCodeObject(test))

        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        self.assertEqual(target(), 1)
        self.assertEqual(INVOKED, 1)
        INVOKED = False

    def test_insert_method_local_capture_3(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            a = 1
            b = 2
            return a

        def test():
            x = capture_local("a")
            y = capture_local("b")
            global INVOKED
            INVOKED = x + y
            x = 2

        self.assertEqual(target(), 1)

        helper = BytecodePatchHelper(target)

        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(4, MutableCodeObject(test))
        else:
            helper.insertMethodAt(5, MutableCodeObject(test))

        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        self.assertEqual(
            target(), 2, "local rebind not fully functional; write back failed!"
        )
        self.assertEqual(INVOKED, 3)
        INVOKED = False

    def test_insert_method_local_capture_static_3(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            a = 1
            b = 2
            return a

        def test():
            x = capture_local_static("a")
            y = capture_local("b")
            global INVOKED
            INVOKED = x + y
            x = 2

        self.assertEqual(target(), 1)

        helper = BytecodePatchHelper(target)
        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(4, MutableCodeObject(test))
        else:
            helper.insertMethodAt(5, MutableCodeObject(test))
        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        self.assertEqual(target(), 1)
        self.assertEqual(INVOKED, 3)
        INVOKED = False

    def test_insert_method_local_capture_4(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            a = 1
            return a

        def test():
            global INVOKED
            INVOKED = capture_local("a")

        helper = BytecodePatchHelper(target)
        if sys.version_info.major <= 3 and sys.version_info.minor < 11:
            helper.insertMethodAt(2, MutableCodeObject(test))
        else:
            helper.insertMethodAt(3, MutableCodeObject(test))
        helper.store()
        helper.patcher.applyPatches()

        global INVOKED
        INVOKED = False
        self.assertEqual(target(), 1)
        self.assertEqual(INVOKED, 1)
        INVOKED = False

    def test_injected_early_exit_1(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target():
            return 1

        def test():
            injected_return(0)
            return -1

        helper = BytecodePatchHelper(target)
        helper.insertMethodAt(0, test)
        helper.store()
        helper.patcher.applyPatches()

        self.assertEqual(target(), 0)

    def test_injected_early_exit_2(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target(c: bool):
            return 1

        def test():
            a = capture_local("c")
            if a:
                injected_return(0)

        # dis.dis(test)

        helper = BytecodePatchHelper(target)
        helper.insertMethodAt(0, test)
        helper.store()
        helper.patcher.applyPatches()

        # dis.dis(target)

        self.assertEqual(target(True), 0)
        self.assertEqual(target(False), 1)

    def test_injected_early_exit_3(self):
        from bytecodemanipulation.TransformationHelper import (
            MutableCodeObject,
            BytecodePatchHelper,
        )

        def target(c: bool):
            return c

        def test():
            a = capture_local("c")
            if a:
                injected_return(0)
            a = 2

        helper = BytecodePatchHelper(target)
        helper.insertMethodAt(0, test)
        helper.store()
        helper.patcher.applyPatches()

        self.assertEqual(target(True), 0)
        self.assertEqual(target(False), 2)
