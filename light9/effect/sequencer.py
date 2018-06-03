'''
copies from effectloop.py, which this should replace
'''

from __future__ import division
from rdflib import URIRef, Literal
from twisted.internet import reactor, defer
from webcolors import rgb_to_hex
import json, logging, bisect
import treq
import math
import time
from twisted.internet.inotify import INotify
from twisted.python.filepath import FilePath
from louie import dispatcher

from light9 import networking
from light9.namespaces import L9, RDF
from light9.vidref.musictime import MusicTime
from light9.effect import effecteval
from light9.effect.settings import DeviceSettings
from light9.effect.simple_outputs import SimpleOutputs

from greplin import scales
from txzmq import ZmqEndpoint, ZmqFactory, ZmqPushConnection

log = logging.getLogger('sequencer')
stats = scales.collection('/sequencer/',
                          scales.PmfStat('update'),
                          scales.PmfStat('compileGraph'),
                          scales.PmfStat('compileSong'),
                          scales.DoubleStat('recentFps'),
)

_zmqClient=None
class TwistedZmqClient(object):
    def __init__(self, service):
        zf = ZmqFactory()
        e = ZmqEndpoint('connect', 'tcp://%s:%s' % (service.host, service.port))
        self.conn = ZmqPushConnection(zf, e)
        
    def send(self, msg):
        self.conn.push(msg)


def toCollectorJson(client, session, settings):
    assert isinstance(settings, DeviceSettings)
    return json.dumps({'settings': settings.asList(),
                       'client': client,
                       'clientSession': session,
                       'sendTime': time.time(),
                  })
        
def sendToCollectorZmq(msg):
    global _zmqClient
    if _zmqClient is None:
        _zmqClient = TwistedZmqClient(networking.collectorZmq)
    _zmqClient.send(msg)
    return defer.succeed(0)
        
def sendToCollector(client, session, settings, useZmq=True):
    """deferred to the time in seconds it took to get a response from collector"""
    sendTime = time.time()
    msg = toCollectorJson(client, session, settings)

    if useZmq:
        d = sendToCollectorZmq(msg)
    else:
        d = treq.put(networking.collector.path('attrs'), data=msg)
    
    def onDone(result):
        dt = time.time() - sendTime
        if dt > .1:
            log.warn('sendToCollector request took %.1fms', dt * 1000)
        return dt
    d.addCallback(onDone)
    def onErr(err):
        log.warn('sendToCollector failed: %r', err)
    d.addErrback(onErr)
    return d


class Note(object):
    def __init__(self, graph, uri, effectevalModule, simpleOutputs):
        g = self.graph = graph
        self.uri = uri
        self.effectEval = effectevalModule.EffectEval(
            graph, g.value(uri, L9['effectClass']), simpleOutputs)
        self.baseEffectSettings = {}  # {effectAttr: value}
        for s in g.objects(uri, L9['setting']):
            settingValues = dict(g.predicate_objects(s))
            ea = settingValues[L9['effectAttr']]
            self.baseEffectSettings[ea] = settingValues[L9['value']]
            
        floatVal = lambda s, p: float(g.value(s, p).toPython())
        originTime = floatVal(uri, L9['originTime'])
        self.points = []
        for curve in g.objects(uri, L9['curve']):
            self.points.extend(
                self.getCurvePoints(curve, L9['strength'], originTime))
        self.points.sort()

    def getCurvePoints(self, curve, attr, originTime):
        points = []
        po = list(self.graph.predicate_objects(curve))
        if dict(po).get(L9['attr'], None) != attr:
            return []
        for point in [row[1] for row in po if row[0] == L9['point']]:
            po2 = dict(self.graph.predicate_objects(point))
            points.append((
                originTime + float(po2[L9['time']]),
                float(po2[L9['value']])))
        return points
            
    def activeAt(self, t):
        return self.points[0][0] <= t <= self.points[-1][0]

    def evalCurve(self, t):
        i = bisect.bisect_left(self.points, (t, None)) - 1

        if i == -1:
            return self.points[0][1]
        if self.points[i][0] > t:
            return self.points[i][1]
        if i >= len(self.points) - 1:
            return self.points[i][1]

        p1, p2 = self.points[i], self.points[i + 1]
        frac = (t - p1[0]) / (p2[0] - p1[0])
        y = p1[1] + (p2[1] - p1[1]) * frac
        return y
        
    def outputSettings(self, t):
        """
        list of (device, attr, value), and a report for web
        """
        report = {'note': str(self.uri)}
        effectSettings = self.baseEffectSettings.copy()
        effectSettings[L9['strength']] = self.evalCurve(t)
        report['effectSettings'] = dict(
            (str(k), str(v))
            for k,v in sorted(effectSettings.items()))
        out = self.effectEval.outputFromEffect(
            effectSettings.items(),
            songTime=t,
            # note: not using origin here since it's going away
            noteTime=t - self.points[0][0])
        print 'out', out.asList()
        return out, report


class CodeWatcher(object):
    def __init__(self, onChange):
        self.onChange = onChange

        self.notifier = INotify()
        self.notifier.startReading()
        self.notifier.watch(
            FilePath(effecteval.__file__.replace('.pyc', '.py')),
            callbacks=[self.codeChange])

    def codeChange(self, watch, path, mask):
        def go():
            log.info("reload effecteval")
            reload(effecteval)
            self.onChange()
        # in case we got an event at the start of the write
        reactor.callLater(.1, go) 
    
        

class Sequencer(object):
    def __init__(self, graph, sendToCollector, fps=40):
        self.graph = graph
        self.fps = fps
        self.sendToCollector = sendToCollector
        self.music = MusicTime(period=.2, pollCurvecalc=False)

        self.recentUpdateTimes = []
        self.lastStatLog = 0
        self._compileGraphCall = None
        self.notes = {} # song: [notes]
        self.simpleOutputs = SimpleOutputs(self.graph)
        self.graph.addHandler(self.compileGraph)
        self.update()

        self.codeWatcher = CodeWatcher(
            onChange=lambda: self.graph.addHandler(self.compileGraph))

    @stats.compileGraph.time()
    def compileGraph(self):
        """rebuild our data from the graph"""
        t1 = time.time()
        g = self.graph

        for song in g.subjects(RDF.type, L9['Song']):
            self.graph.addHandler(lambda song=song: self.compileSong(song))
        log.info('compileGraph took %.2f ms', 1000 * (time.time() - t1))
        
    @stats.compileSong.time()
    def compileSong(self, song):
        t1 = time.time()

        self.notes[song] = []
        for note in self.graph.objects(song, L9['note']):
            self.notes[song].append(Note(self.graph, note, effecteval,
                                         self.simpleOutputs))
        log.info('  compile %s took %.2f ms', song, 1000 * (time.time() - t1))

        
    @stats.update.time()
    def update(self):
        now = time.time()
        self.recentUpdateTimes = self.recentUpdateTimes[-20:] + [now]
        stats.recentFps = len(self.recentUpdateTimes) / (self.recentUpdateTimes[-1] - self.recentUpdateTimes[0] + .0001)
        if now > self.lastStatLog + 10:
            dispatcher.send('state', update={'recentFps': stats.recentFps})
            self.lastStatLog = now
        
        reactor.callLater(1 / self.fps, self.update)

        musicState = self.music.getLatest()
        song = URIRef(musicState['song']) if musicState.get('song') else None
        dispatcher.send('state', update={'song': str(song)})
        if 't' not in musicState:
            return
        t = musicState['t']

        settings = []
        songNotes = sorted(self.notes.get(song, []))
        noteReports = []
        for note in songNotes:
            s, report = note.outputSettings(t)
            noteReports.append(report)
            settings.append(s)
        dispatcher.send('state', update={'songNotes': noteReports})
        self.sendToCollector(DeviceSettings.fromList(self.graph, settings))

import cyclone.sse
class Updates(cyclone.sse.SSEHandler):
    def __init__(self, application, request, **kwargs):
        cyclone.sse.SSEHandler.__init__(self, application, request,
                                        **kwargs)
        self.state = {}
        dispatcher.connect(self.updateState, 'state')
        self.numConnected = 0

    def updateState(self, update):
        self.state.update(update)
        
    def bind(self):
        print 'new client', self.settings.seq
        self.numConnected += 1
        
        if self.numConnected == 1:
            self.loop()

    def loop(self):
        if self.numConnected == 0:
            return
        self.sendEvent(self.state)
        reactor.callLater(2, self.loop)
        
    def unbind(self):
        self.numConnected -= 1
        print 'bye', self.numConnected
    
