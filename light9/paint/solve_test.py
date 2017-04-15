import unittest
import solve

class TestSolve(unittest.TestCase):
    def testBlack(self):
        s = solve.Solver()
        s.loadSamples()
        devAttrs = s.solve({'strokes': []})
        self.assertEqual([], devAttrs)


        
