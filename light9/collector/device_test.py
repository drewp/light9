import unittest
from rdflib import Literal
from light9.namespaces import L9

from light9.collector.device import toOutputAttrs

class TestColorStrip(unittest.TestCase):
    def testConvertDeviceToOutputAttrs(self):
        out = toOutputAttrs(L9['ChauvetColorStrip'],
                            {L9['color']: Literal('#ff0000')})
        self.assertEqual({L9['mode']: 215,
                          L9['red']: 255,
                          L9['green']: 0,
                          L9['blue']: 0
                      }, out)
        
class TestDimmer(unittest.TestCase):
    def testConvert(self):
        self.assertEqual({L9['brightness']: 127},
                         toOutputAttrs(L9['Dimmer'], {L9['brightness']: .5}))

class TestMini15(unittest.TestCase):
    def testConvertColor(self):
        out = toOutputAttrs(L9['Mini15'], {L9['color']: '#010203'})
        self.assertEqual(255, out[L9['dimmer']])
        self.assertEqual(1, out[L9['red']])
        self.assertEqual(2, out[L9['green']])
        self.assertEqual(3, out[L9['blue']])
    def testConvertRotation(self):
        out = toOutputAttrs(L9['Mini15'], {L9['rx']: Literal(90), L9['ry']: Literal(45)})
        self.assertEqual(42, out[L9['xRotation']])
        self.assertEqual(31, out[L9['xFine']])
        self.assertEqual(47, out[L9['yRotation']])
        self.assertEqual(51, out[L9['yFine']])
        self.assertEqual(0, out[L9['rotationSpeed']])
