import unittest
import solve
from light9.namespaces import RDF, L9, DEV
from light9.rdfdb.localsyncedgraph import LocalSyncedGraph

class TestSolve(unittest.TestCase):
    def setUp(self):
        graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        self.solver = solve.Solver(graph)
        self.solver.loadSamples()

    def testBlack(self):
        devAttrs = self.solver.solve({'strokes': []})
        self.assertEqual([], devAttrs)

    def testSingleLightCloseMatch(self):
        devAttrs = self.solver.solve({'strokes': [{'pts': [[224, 141],
                                                 [223, 159]],
                                         'color': '#ffffff'}]})
        self.assertItemsEqual([
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573),
        ], devAttrs)
        
        
class TestSimulationLayers(unittest.TestCase):
    def setUp(self):
        graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        self.solver = solve.Solver(graph)
        self.solver.loadSamples()
        
    def testBlack(self):
        self.assertEqual([], self.solver.simulationLayers(settings=[]))

    def testPerfect1Match(self):
        layers = self.solver.simulationLayers(settings=[
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573)])
        self.assertEqual([{'path': 'bg2-d.jpg', 'color': (1, 1, 1)}], layers)

    def testPerfect1MatchTinted(self):
        layers = self.solver.simulationLayers(settings=[
            (DEV['aura1'], L9['color'], u"#304050"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573)])
        self.assertEqual([{'path': 'bg2-d.jpg', 'color': (.188, .251, .314)}], layers)
        
    def testPerfect2Matches(self):
        layers = self.solver.simulationLayers(settings=[
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573),
            (DEV['aura2'], L9['color'], u"#ffffff"),
            (DEV['aura2'], L9['rx'], 0.7 ),
            (DEV['aura2'], L9['ry'], 0.573),
        ])
        self.assertItemsEqual([
            {'path': 'bg2-d.jpg', 'color': (1, 1, 1)},
            {'path': 'bg2-f.jpg', 'color': (1, 1, 1)},
                      ], layers)
