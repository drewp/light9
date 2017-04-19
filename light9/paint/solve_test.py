import unittest
import solve
from light9.namespaces import RDF, L9, DEV
from light9.rdfdb.localsyncedgraph import LocalSyncedGraph

class TestSolve(unittest.TestCase):
    def testBlack(self):
        graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        s = solve.Solver(graph)
        s.loadSamples()
        devAttrs = s.solve({'strokes': []})
        self.assertEqual([], devAttrs)

    def testSingleLightCloseMatch(self):
        graph = LocalSyncedGraph(files=['show/dance2017/cam/test/bg.n3'])
        s = solve.Solver(graph)
        s.loadSamples()
        devAttrs = s.solve({'strokes': [{'pts': [[224, 141],
                                                 [223, 159]],
                                         'color': '#ffffff'}]})
        self.assertEqual(sorted([
            (DEV['aura1'], L9['color'], u"#ffffff"),
            (DEV['aura1'], L9['rx'], 0.5 ),
            (DEV['aura1'], L9['ry'], 0.573),
        ]), sorted(devAttrs))
        
        
