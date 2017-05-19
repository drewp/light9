import unittest
from light9.rdfdb.localsyncedgraph import LocalSyncedGraph
from light9.namespaces import RDF, L9, DEV
from light9.effect.settings import DeviceSettings

class TestDeviceSettings(unittest.TestCase):
    def setUp(self):
        self.graph = LocalSyncedGraph(files=['show/dance2017/cam/test/lightConfig.n3',
                                             'show/dance2017/cam/test/bg.n3'])

    def testToVectorZero(self):
        ds = DeviceSettings(self.graph, [])
        self.assertEqual([0] * 20, ds.toVector())
