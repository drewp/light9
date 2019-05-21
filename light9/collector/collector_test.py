import unittest
import datetime, time
from freezegun import freeze_time
from rdflib import Namespace, URIRef

from light9.namespaces import L9, DEV
from light9.collector.collector import Collector, outputMap
from rdfdb.mock_syncedgraph import MockSyncedGraph

UDMX = Namespace('http://light9.bigasterisk.com/output/udmx/')
DMX0 = Namespace('http://light9.bigasterisk.com/output/dmx0/')

PREFIX = '''
   @prefix : <http://light9.bigasterisk.com/> .
        @prefix dev: <http://light9.bigasterisk.com/device/> .
        @prefix udmx: <http://light9.bigasterisk.com/output/udmx/> .
        @prefix dmx0: <http://light9.bigasterisk.com/output/dmx0/> .
'''

THEATER = '''
        :brightness         a :DeviceAttr; :dataType :scalar .

        :SimpleDimmer a :DeviceClass;
          :deviceAttr :brightness;
          :attr
            [ :outputAttr :level; :dmxOffset 0 ] .
                
        :ChauvetColorStrip a :DeviceClass;
          :deviceAttr :color;
          :attr
            [ :outputAttr :mode;  :dmxOffset 0 ],
            [ :outputAttr :red;   :dmxOffset 1 ],
            [ :outputAttr :green; :dmxOffset 2 ],
            [ :outputAttr :blue;  :dmxOffset 3 ] .

'''

t0 = 0  # time


class MockOutput(object):

    def __init__(self, uri, connections):
        self.connections = connections
        self.updates = []
        self.uri = uri
        self.numChannels = 4

    def allConnections(self):
        return self.connections

    def update(self, values):
        self.updates.append(values)

    def flush(self):
        self.updates.append('flush')


@unittest.skip("outputMap got rewritten and mostly doesn't raise on these cases"
              )
class TestOutputMap(unittest.TestCase):

    def testWorking(self):
        out0 = MockOutput(UDMX, [(0, DMX0['c1'])])
        m = outputMap(
            MockSyncedGraph(PREFIX + '''
          dmx0:c1 :connectedTo dev:inst1Brightness .
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])
        self.assertEqual({(DEV['inst1'], L9['brightness']): (out0, 0)}, m)

    def testMissingOutput(self):
        out0 = MockOutput(UDMX, [(0, DMX0['c1'])])
        self.assertRaises(
            KeyError, outputMap,
            MockSyncedGraph(PREFIX + '''
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])

    def testMissingOutputConnection(self):
        out0 = MockOutput(UDMX, [(0, DMX0['c1'])])
        self.assertRaises(
            ValueError, outputMap,
            MockSyncedGraph(PREFIX + '''
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])

    def testMultipleOutputConnections(self):
        out0 = MockOutput(UDMX, [(0, DMX0['c1'])])
        self.assertRaises(
            ValueError, outputMap,
            MockSyncedGraph(PREFIX + '''
          dmx0:c1 :connectedTo dev:inst1Brightness .
          dmx0:c2 :connectedTo dev:inst1Brightness .
          dev:inst1 a :Device; :brightness dev:inst1Brightness .
        '''), [out0])


class TestCollector(unittest.TestCase):

    def setUp(self):
        self.config = MockSyncedGraph(PREFIX + THEATER + '''

        dev:colorStrip a :Device, :ChauvetColorStrip;
          :dmxUniverse udmx:; :dmxBase 1;
          :red dev:colorStripRed;
          :green dev:colorStripGreen;
          :blue dev:colorStripBlue;
          :mode dev:colorStripMode .

        dev:inst1 a :Device, :SimpleDimmer;
          :dmxUniverse dmx0:; :dmxBase 1;
          :level dev:inst1Brightness .
        ''')

        self.dmx0 = MockOutput(DMX0[None], [(0, DMX0['c1'])])
        self.udmx = MockOutput(UDMX[None], [(0, UDMX['c1']), (1, UDMX['c2']),
                                            (2, UDMX['c3']), (3, UDMX['c4'])])

    def testRoutesColorOutput(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#00ff00')], t0)

        self.assertEqual([[215, 0, 255, 0], 'flush'], self.udmx.updates)
        self.assertEqual([[0, 0, 0, 0], 'flush'], self.dmx0.updates)

    def testOutputMaxOfTwoClients(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#ff0000')], t0)
        c.setAttrs('client2', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#333333')], t0)

        self.assertEqual(
            [[215, 255, 0, 0], 'flush', [215, 255, 51, 51], 'flush'],
            self.udmx.updates)
        self.assertEqual([[0, 0, 0, 0], 'flush', [0, 0, 0, 0], 'flush'],
                         self.dmx0.updates)

    def testClientOnSameOutputIsRememberedOverCalls(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#080000')], t0)
        c.setAttrs('client2', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#060000')], t0)
        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#050000')], t0)

        self.assertEqual([[215, 8, 0, 0], 'flush', [215, 8, 0, 0], 'flush',
                          [215, 6, 0, 0], 'flush'], self.udmx.updates)
        self.assertEqual([[0, 0, 0, 0], 'flush', [0, 0, 0, 0], 'flush',
                          [0, 0, 0, 0], 'flush'], self.dmx0.updates)

    def testClientsOnDifferentOutputs(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#aa0000')], t0)
        c.setAttrs('client2', 'sess1', [(DEV['inst1'], L9['brightness'], .5)],
                   t0)

        # ok that udmx is flushed twice- it can screen out its own duplicates
        self.assertEqual([[215, 170, 0, 0], 'flush', [215, 170, 0, 0], 'flush'],
                         self.udmx.updates)
        self.assertEqual([[0, 0, 0, 0], 'flush', [127, 0, 0, 0], 'flush'],
                         self.dmx0.updates)

    def testNewSessionReplacesPreviousOutput(self):
        # ..as opposed to getting max'd with it
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [(DEV['inst1'], L9['brightness'], .8)],
                   t0)
        c.setAttrs('client1', 'sess2', [(DEV['inst1'], L9['brightness'], .5)],
                   t0)

        self.assertEqual([[204, 0, 0, 0], 'flush', [127, 0, 0, 0], 'flush'],
                         self.dmx0.updates)

    def testNewSessionDropsPreviousSettingsOfOtherAttrs(self):
        c = Collector(MockSyncedGraph(PREFIX + THEATER + '''

        dev:colorStrip a :Device, :ChauvetColorStrip;
          :dmxUniverse udmx:; :dmxBase 1;
          :red dev:colorStripRed;
          :green dev:colorStripGreen;
          :blue dev:colorStripBlue;
          :mode dev:colorStripMode .

        dev:inst1 a :Device, :SimpleDimmer;
          :dmxUniverse dmx0:; :dmxBase 0;
          :level dev:inst1Brightness .
        '''),
                      outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#ff0000')], t0)
        c.setAttrs('client1', 'sess2',
                   [(DEV['colorStrip'], L9['color'], '#00ff00')], t0)

        self.assertEqual([[215, 255, 0, 0], 'flush', [215, 0, 255, 0], 'flush'],
                         self.udmx.updates)

    def testClientIsForgottenAfterAWhile(self):
        with freeze_time(datetime.datetime.now()) as ft:
            c = Collector(self.config, outputs=[self.dmx0, self.udmx])
            c.setAttrs('cli1', 'sess1', [(DEV['inst1'], L9['brightness'], .5)],
                       time.time())
            ft.tick(delta=datetime.timedelta(seconds=1))
            # this max's with cli1's value so we still see .5
            c.setAttrs('cli2', 'sess1', [(DEV['inst1'], L9['brightness'], .2)],
                       time.time())
            ft.tick(delta=datetime.timedelta(seconds=9.1))
            # now cli1 is forgotten, so our value appears
            c.setAttrs('cli2', 'sess1', [(DEV['inst1'], L9['brightness'], .4)],
                       time.time())
            self.assertEqual([[127, 0, 0, 0], 'flush', [127, 0, 0, 0], 'flush',
                              [102, 0, 0, 0], 'flush'], self.dmx0.updates)

    def testClientUpdatesAreNotMerged(self):
        # second call to setAttrs forgets the first
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])
        t0 = time.time()
        c.setAttrs('client1', 'sess1', [(DEV['inst1'], L9['brightness'], .5)],
                   t0)
        c.setAttrs('client1', 'sess1', [(DEV['inst1'], L9['brightness'], 1)],
                   t0)
        c.setAttrs('client1', 'sess1',
                   [(DEV['colorStrip'], L9['color'], '#00ff00')], t0)

        self.assertEqual([[215, 0, 0, 0], 'flush', [215, 0, 0, 0], 'flush',
                          [215, 0, 255, 0], 'flush'], self.udmx.updates)
        self.assertEqual([[127, 0, 0, 0], 'flush', [255, 0, 0, 0], 'flush',
                          [0, 0, 0, 0], 'flush'], self.dmx0.updates)

    def testRepeatedAttributesInOneRequestGetResolved(self):
        c = Collector(self.config, outputs=[self.dmx0, self.udmx])

        c.setAttrs('client1', 'sess1', [
            (DEV['inst1'], L9['brightness'], .5),
            (DEV['inst1'], L9['brightness'], .3),
        ], t0)
        self.assertEqual([[127, 0, 0, 0], 'flush'], self.dmx0.updates)

        c.setAttrs('client1', 'sess1', [
            (DEV['inst1'], L9['brightness'], .3),
            (DEV['inst1'], L9['brightness'], .5),
        ], t0)
        self.assertEqual([[127, 0, 0, 0], 'flush', [127, 0, 0, 0], 'flush'],
                         self.dmx0.updates)
