import unittest
from light9.namespaces import L9
from light9.collector.output import setListElem, DmxOutput


class TestSetListElem(unittest.TestCase):

    def testSetExisting(self):
        x = [0, 1]
        setListElem(x, 0, 9)
        self.assertEqual([9, 1], x)

    def testSetNext(self):
        x = [0, 1]
        setListElem(x, 2, 9)
        self.assertEqual([0, 1, 9], x)

    def testSetBeyond(self):
        x = [0, 1]
        setListElem(x, 3, 9)
        self.assertEqual([0, 1, 0, 9], x)

    def testArbitraryFill(self):
        x = [0, 1]
        setListElem(x, 5, 9, fill=8)
        self.assertEqual([0, 1, 8, 8, 8, 9], x)

    def testSetZero(self):
        x = [0, 1]
        setListElem(x, 5, 0)
        self.assertEqual([0, 1, 0, 0, 0, 0], x)

    def testCombineMax(self):
        x = [0, 1]
        setListElem(x, 1, 0, combine=max)
        self.assertEqual([0, 1], x)

    def testCombineHasNoEffectOnNewElems(self):
        x = [0, 1]
        setListElem(x, 2, 1, combine=max)
        self.assertEqual([0, 1, 1], x)


class TestDmxOutput(unittest.TestCase):

    def testFlushIsNoop(self):
        out = DmxOutput(L9['output/udmx/'], 3)
        out.flush()
