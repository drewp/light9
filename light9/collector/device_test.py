import unittest
from rdflib import Literal
from light9.namespaces import L9

from light9.collector.device import toOutputAttrs, resolve

class TestUnknownDevice(unittest.TestCase):
    def testFails(self):
        self.assertRaises(NotImplementedError, toOutputAttrs, L9['bogus'], {})

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
        self.assertEqual({L9['level']: 127},
                         toOutputAttrs(L9['SimpleDimmer'], {L9['brightness']: .5}))

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
        self.assertEqual(127, out[L9['xFine']])
        self.assertEqual(47, out[L9['yRotation']])
        self.assertEqual(51, out[L9['yFine']])
        self.assertEqual(0, out[L9['rotationSpeed']])
        
class TestResolve(unittest.TestCase):
    def testMaxes1Color(self):
        # do not delete - this one catches a bug in the rgb_to_hex(...) lines
        self.assertEqual('#ff0300',
                         resolve(None, L9['color'], ['#ff0300']))
    def testMaxes2Colors(self):
        self.assertEqual('#ff0400',
                         resolve(None, L9['color'], ['#ff0300', '#000400']))
    def testMaxes3Colors(self):
        self.assertEqual('#112233',
                         resolve(None, L9['color'],
                                 ['#110000', '#002200', '#000033']))
        
