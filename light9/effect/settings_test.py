import unittest
from rdflib import Literal
from light9.rdfdb.patch import Patch
from light9.rdfdb.localsyncedgraph import LocalSyncedGraph
from light9.namespaces import RDF, L9, DEV
from light9.effect.settings import DeviceSettings

class TestDeviceSettings(unittest.TestCase):
    def setUp(self):
        self.graph = LocalSyncedGraph(files=['show/dance2017/cam/test/lightConfig.n3',
                                             'show/dance2017/cam/test/bg.n3'])

    def testToVectorZero(self):
        ds = DeviceSettings(self.graph, [])
        self.assertEqual([0] * 30, ds.toVector())

    def testEq(self):
        s1 = DeviceSettings(self.graph, [
            (L9['light1'], L9['attr1'], 0.5),
            (L9['light1'], L9['attr2'], 0.3),
        ])
        s2 = DeviceSettings(self.graph, [
            (L9['light1'], L9['attr2'], 0.3),
            (L9['light1'], L9['attr1'], 0.5),
        ])
        self.assertTrue(s1 == s2)
        self.assertFalse(s1 != s2)

    def testMissingFieldsEqZero(self):
        self.assertEqual(
            DeviceSettings(self.graph, [(L9['aura1'], L9['rx'], 0),]),
            DeviceSettings(self.graph, []))

    def testFalseIfZero(self):
        self.assertTrue(DeviceSettings(self.graph, [(L9['aura1'], L9['rx'], 0.1)]))
        self.assertFalse(DeviceSettings(self.graph, []))
        
    def testFromResource(self):
        ctx = L9['']
        self.graph.patch(Patch(addQuads=[
            (L9['foo'], L9['setting'], L9['foo_set0'], ctx),
            (L9['foo_set0'], L9['device'], L9['light1'], ctx),
            (L9['foo_set0'], L9['deviceAttr'], L9['brightness'], ctx),
            (L9['foo_set0'], L9['value'], Literal(0.1), ctx),
            (L9['foo'], L9['setting'], L9['foo_set1'], ctx),
            (L9['foo_set1'], L9['device'], L9['light1'], ctx),
            (L9['foo_set1'], L9['deviceAttr'], L9['speed'], ctx),
            (L9['foo_set1'], L9['scaledValue'], Literal(0.2), ctx),
        ]))
        s = DeviceSettings.fromResource(self.graph, L9['foo'])

        self.assertEqual(DeviceSettings(self.graph, [
            (L9['light1'], L9['brightness'], 0.1),
            (L9['light1'], L9['speed'], 0.2),
        ]), s)

    def testToVector(self):
        v = DeviceSettings(self.graph, [
            (DEV['aura1'], L9['rx'], 0.5),
            (DEV['aura1'], L9['color'], '#00ff00'),
        ]).toVector()
        self.assertEqual(
            [0, 1, 0, 0.5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            v)
        
    def testFromVector(self):
        s = DeviceSettings.fromVector(
            self.graph,
            [0, 1, 0, 0.5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        
        self.assertEqual(DeviceSettings(self.graph, [
            (DEV['aura1'], L9['rx'], 0.5),
            (DEV['aura1'], L9['color'], '#00ff00'),
        ]), s)                            

    def testAsList(self):
        sets = [
            (L9['light1'], L9['attr2'], 0.3),
            (L9['light1'], L9['attr1'], 0.5),
        ]
        self.assertItemsEqual(sets, DeviceSettings(self.graph, sets).asList())

    def testDevices(self):
        s = DeviceSettings(self.graph, [
            (DEV['aura1'], L9['rx'], 0),
            (DEV['aura2'], L9['rx'], 0.1),
            ])
        # aura1 is all defaults (zeros), so it doesn't get listed
        self.assertItemsEqual([DEV['aura2']], s.devices())

    def testAddStatements(self):
        s = DeviceSettings(self.graph, [
            (DEV['aura2'], L9['rx'], 0.1),
            ])
        stmts = s.statements(L9['foo'], L9['ctx1'], L9['s_'], set())
        self.maxDiff=None
        self.assertItemsEqual([
            (L9['foo'], L9['setting'], L9['s_set4350023'], L9['ctx1']),
            (L9['s_set4350023'], L9['device'], DEV['aura2'], L9['ctx1']),
            (L9['s_set4350023'], L9['deviceAttr'], L9['rx'], L9['ctx1']),
            (L9['s_set4350023'], L9['value'], Literal(0.1), L9['ctx1']),
        ], stmts)
        
    def testDistanceTo(self):
        s1 = DeviceSettings(self.graph, [
            (DEV['aura1'], L9['rx'], 0.1),
            (DEV['aura1'], L9['ry'], 0.6),
        ])
        s2 = DeviceSettings(self.graph, [
            (DEV['aura1'], L9['rx'], 0.3),
            (DEV['aura1'], L9['ry'], 0.3),
        ])
        self.assertEqual(0.36055512754639896, s1.distanceTo(s2))
        
