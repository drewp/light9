import unittest
import datetime
from freezegun import freeze_time
from rdflib import  Literal, Graph, Namespace
from rdflib.parser import StringInputSource

from light9.namespaces import L9, DEV
from light9.collector.collector import Collector, outputMap

UDMX = Namespace('http://light9.bigasterisk.com/output/udmx/')
DMX0 = Namespace('http://light9.bigasterisk.com/output/dmx0/')


def fromN3(n3):
    out = Graph()
    out.parse(StringInputSource('''
        @prefix : <http://light9.bigasterisk.com/> .
        @prefix dev: <http://light9.bigasterisk.com/device/> .
        @prefix udmx: <http://light9.bigasterisk.com/output/udmx/> .
        @prefix dmx0: <http://light9.bigasterisk.com/output/dmx0/> .
    ''' + n3), format='n3')
    return out

class MockOutput(object):
    def __init__(self, connections):
        self.connections = connections
        self.updates = []

    def allConnections(self):
        return self.connections
    
    def update(self, values):
        self.updates.append(values)

    def flush(self):
        self.updates.append('flush')

class TestOutputMap(unittest.TestCase):
    def testWorking(self):
        out0 = MockOutput([(0, DMX0['c1'])])
        m = outputMap(fromN3('''
          dmx0:c1 :connectedTo dev:inst1Brightness .
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])
        self.assertEqual({(DEV['inst1'], L9['brightness']): (out0, 0)}, m)
    def testMissingOutput(self):
        out0 = MockOutput([(0, DMX0['c1'])])
        self.assertRaises(KeyError, outputMap, fromN3('''
          dmx0:c2 :connectedTo dev:inst1Brightness .
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])

    def testMissingOutputConnection(self):
        out0 = MockOutput([(0, DMX0['c1'])])
        self.assertRaises(ValueError, outputMap, fromN3('''
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])

    def testMultipleOutputConnections(self):
        out0 = MockOutput([(0, DMX0['c1'])])
        self.assertRaises(ValueError, outputMap, fromN3('''
          dmx0:c1 :connectedTo dev:inst1Brightness .
          dmx0:c2 :connectedTo dev:inst1Brightness .
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])
        
        
        
class TestCollector(unittest.TestCase):
    def setUp(self):
        self.config = fromN3('''
        
        udmx:c1 :connectedTo dev:colorStripRed .
        udmx:c2 :connectedTo dev:colorStripGreen .
        udmx:c3 :connectedTo dev:colorStripBlue .
        udmx:c4 :connectedTo dev:colorStripMode .

        dev:colorStrip a :Device;
          :red dev:colorStripRed;
          :green dev:colorStripGreen;
          :blue dev:colorStripBlue;
          :mode dev:colorStripMode .

        dmx0:c1 :connectedTo dev:inst1Brightness .
        dev:inst1 a :Device;
          :brightness dev:inst1Brightness .
        ''')

        self.dmx0 = MockOutput([(0, DMX0['c1'])])
        self.udmx = MockOutput([(0, UDMX['c1']),
                                (1, UDMX['c2']),
                                (2, UDMX['c3']),
                                (3, UDMX['c4'])])

    def testRoutesSimpleOutput(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client', 'sess1',
                   [(DEV['colorStrip'], L9['green'], Literal(1.0))])

        self.assertEqual([[0, 255, 0, 215], 'flush'], self.udmx.updates)
        self.assertEqual([], self.dmx0.updates)

    def testRoutesColorOutput(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client', 'sess1',
                   [(DEV['colorStrip'], L9['color'], Literal('#ff0000'))])

        self.assertEqual([[255, 0, 0, 215], 'flush'], self.udmx.updates)
        self.assertEqual([], self.dmx0.updates)

    def testOutputMaxOfTwoClients(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], Literal('#ff0000'))])
        c.setAttrs('client2', 'sess1',
                   [(DEV['colorStrip'], L9['color'], Literal('#333333'))])

        self.assertEqual([[255, 0, 0, 215], 'flush',
                          [255, 51, 51, 215], 'flush'],
                         self.udmx.updates)
        self.assertEqual([], self.dmx0.updates)
        
    def testClientOnSameOutputIsRememberedOverCalls(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [(DEV['colorStrip'], L9['red'], .8)])
        c.setAttrs('client2', 'sess1', [(DEV['colorStrip'], L9['red'], .6)])
        c.setAttrs('client1', 'sess1', [(DEV['colorStrip'], L9['red'], .5)])
        
        self.assertEqual([[204, 0, 0, 215], 'flush',
                          [204, 0, 0, 215], 'flush',
                          [153, 0, 0, 215], 'flush'],
                         self.udmx.updates)
        self.assertEqual([], self.dmx0.updates)
        
    def testClientsOnDifferentOutputs(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [(DEV['colorStrip'], L9['red'], .8)])
        c.setAttrs('client2', 'sess1', [(DEV['inst1'], L9['brightness'], .5)])

        # ok that udmx is flushed twice- it can screen out its own duplicates
        self.assertEqual([[204, 0, 0, 215], 'flush',
                          [204, 0, 0, 215], 'flush'], self.udmx.updates)
        self.assertEqual([[127], 'flush'], self.dmx0.updates)
        
    def testNewSessionReplacesPreviousOutput(self):
        # ..as opposed to getting max'd with it
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [(DEV['inst1'], L9['brightness'], .8)])
        c.setAttrs('client1', 'sess2', [(DEV['inst1'], L9['brightness'], .5)])
        
        self.assertEqual([[204], 'flush', [127], 'flush'], self.dmx0.updates)

    def testNewSessionDropsPreviousSettingsOfOtherAttrs(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [(DEV['colorStrip'], L9['red'], 1)])
        c.setAttrs('client1', 'sess2', [(DEV['colorStrip'], L9['green'], 1)])
        
        self.assertEqual([[255, 0, 0, 215], 'flush',
                          [0, 255, 0, 215], 'flush'], self.udmx.updates)
        
    def testClientIsForgottenAfterAWhile(self):
        with freeze_time(datetime.datetime.now()) as ft:
            c = Collector(self.config, outputs=[self.dmx0, self.udmx])
            c.setAttrs('cli1', 'sess1', [(DEV['inst1'], L9['brightness'], .5)])
            ft.tick(delta=datetime.timedelta(seconds=1))
            c.setAttrs('cli2', 'sess1', [(DEV['inst1'], L9['brightness'], .2)])
            ft.tick(delta=datetime.timedelta(seconds=9.1))
            c.setAttrs('cli2', 'sess1', [(DEV['inst1'], L9['brightness'], .4)])
            self.assertEqual([[127], 'flush', [127], 'flush', [102], 'flush'],
                             self.dmx0.updates)

    def testClientUpdatesAreCollected(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [(DEV['colorStrip'], L9['red'], 1)])
        c.setAttrs('client1', 'sess1', [(DEV['colorStrip'], L9['green'], 1)])
        
        self.assertEqual([[255, 0, 0, 215], 'flush',
                          [255, 255, 0, 215], 'flush'], self.udmx.updates)
        self.assertEqual([], self.dmx0.updates)
