import unittest
import numpy.testing
import solve
from light9.namespaces import RDF, L9, DEV
from light9.rdfdb.localsyncedgraph import LocalSyncedGraph
from light9.effect.settings import DeviceSettings

class TestSolve(unittest.TestCase):
    def setUp(self):
        graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        self.solver = solve.Solver(graph)
        self.solver.loadSamples()
        self.solveMethod = self.solver.solve

    def testBlack(self):
        devAttrs = self.solveMethod({'strokes': []})
        self.assertEqual(DeviceSettings(self.graph, []), devAttrs)

    def testSingleLightCloseMatch(self):
        devAttrs = self.solveMethod({'strokes': [{'pts': [[224, 141],
                                                 [223, 159]],
                                         'color': '#ffffff'}]})
        self.assertEqual(DeviceSettings(self.graph, [
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573),
        ]), devAttrs)

class TestSolveBrute(TestSolve):
    def setUp(self):
        super(TestSolveBrute, self).setUp()
        self.solveMethod = self.solver.solveBrute
        
class TestSimulationLayers(unittest.TestCase):
    def setUp(self):
        self.graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        self.solver = solve.Solver(self.graph)
        self.solver.loadSamples()
        
    def testBlack(self):
        self.assertEqual(
            [],
            self.solver.simulationLayers(settings=DeviceSettings(self.graph, [])))

    def testPerfect1Match(self):
        layers = self.solver.simulationLayers(settings=DeviceSettings(self.graph, [
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573)]))
        self.assertEqual([{'path': 'bg2-d.jpg', 'color': (1., 1., 1.)}], layers)

    def testPerfect1MatchTinted(self):
        layers = self.solver.simulationLayers(settings=DeviceSettings(self.graph, [
            (DEV['aura1'], L9['color'], u"#304050"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573)]))
        self.assertEqual([{'path': 'bg2-d.jpg', 'color': (.188, .251, .314)}], layers)
        
    def testPerfect2Matches(self):
        layers = self.solver.simulationLayers(settings=DeviceSettings(self.graph, [
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573),
            (DEV['aura2'], L9['color'], u"#ffffff"),
            (DEV['aura2'], L9['rx'], 0.7 ),
            (DEV['aura2'], L9['ry'], 0.573),
        ]))
        self.assertItemsEqual([
            {'path': 'bg2-d.jpg', 'color': (1, 1, 1)},
            {'path': 'bg2-f.jpg', 'color': (1, 1, 1)},
                      ], layers)

class TestCombineImages(unittest.TestCase):
    def setUp(self):
        graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        self.solver = solve.Solver(graph)
        self.solver.loadSamples()
    def test(self):
        out = self.solver.combineImages(layers=[
            {'path': 'bg2-d.jpg', 'color': (.2, .2, .3)},
            {'path': 'bg2-a.jpg', 'color': (.888, 0, .3)},
        ])
        solve.saveNumpy('/tmp/t.png', out)
        golden = solve.loadNumpy('show/dance2017/cam/test/layers_out1.png')
        numpy.testing.assert_array_equal(golden, out)

