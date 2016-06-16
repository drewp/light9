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

from light9 import networking
from light9.namespaces import L9, RDF
from light9.vidref.musictime import MusicTime
from light9.effect import effecteval
from greplin import scales
from txzmq import ZmqEndpoint, ZmqFactory, ZmqPushConnection

log = logging.getLogger('sequencer')
stats = scales.collection('/sequencer/',
                          scales.PmfStat('update'),
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
    return json.dumps({'settings': settings,
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
    def __init__(self, graph, uri, effectevalModule, sharedEffectOutputs):
        g = self.graph = graph
        self.uri = uri
        self.effectEval = effectevalModule.EffectEval(
            graph, g.value(uri, L9['effectClass']), sharedEffectOutputs)
        self.baseEffectSettings = {}  # {effectAttr: value}
        for s in g.objects(uri, L9['setting']):
            ea = g.value(s, L9['effectAttr'])
            self.baseEffectSettings[ea] = g.value(s, L9['value'])
            
        floatVal = lambda s, p: float(g.value(s, p).toPython())
        originTime = floatVal(uri, L9['originTime'])
        self.points = []
        for curve in g.objects(uri, L9['curve']):
            if g.value(curve, L9['attr']) != L9['strength']:
                continue
            for point in g.objects(curve, L9['point']):
                self.points.append((
                    originTime + floatVal(point, L9['time']),
                    floatVal(point, L9['value'])))
            self.points.sort()
        
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
        list of (device, attr, value)
        """
        effectSettings = self.baseEffectSettings.copy()
        effectSettings[L9['strength']] = self.evalCurve(t)
        return self.effectEval.outputFromEffect(
            effectSettings.items(),
            songTime=t,
            # note: not using origin here since it's going away
            noteTime=t - self.points[0][0])


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
    def __init__(self, graph, sendToCollector):
        self.graph = graph
        self.sendToCollector = sendToCollector
        self.music = MusicTime(period=.2, pollCurvecalc=False)

        self.recentUpdateTimes = []
        self.lastStatLog = 0
        self._compileGraphCall = None
        self.notes = {} # song: [notes]
        self.graph.addHandler(self.compileGraph)
        self.update()

        self.codeWatcher = CodeWatcher(
            onChange=lambda: self.graph.addHandler(self.compileGraph))

    def compileGraph(self):
        log.info('compileGraph request')
        self._compileGraphRun()
        return

        # may not help
        if self._compileGraphCall:
            self._compileGraphCall.cancel()
        self._compileGraphCall = reactor.callLater(
            .5,
            self.graph.addHandler, self._compileGraphRun)

    def _compileGraphRun(self):
        """rebuild our data from the graph"""
        self._compileGraphCall = None
        log.info('compileGraph start')
        g = self.graph

        sharedEffectOutputs = {}
        
        for song in g.subjects(RDF.type, L9['Song']):
            self.notes[song] = []
            for note in g.objects(song, L9['note']):
                self.notes[song].append(Note(g, note, effecteval, sharedEffectOutputs))
        log.info('compileGraph done')

    @stats.update.time()
    def update(self):
        now = time.time()
        self.recentUpdateTimes = self.recentUpdateTimes[-20:] + [now]
        stats.recentFps = len(self.recentUpdateTimes) / (self.recentUpdateTimes[-1] - self.recentUpdateTimes[0] + .0001)
        if now > self.lastStatLog + 10:
            log.info("%.2f fps", stats.recentFps)
            self.lastStatLog = now
        
        reactor.callLater(1/50, self.update)

        musicState = self.music.getLatest()
        song = URIRef(musicState['song']) if musicState.get('song') else None
        if 't' not in musicState:
            return
        t = musicState['t']

        settings = []
        
        for note in self.notes.get(song, []):
            outs = note.outputSettings(t)
            #print 'out', outs
            settings.extend(outs)
        self.sendToCollector(settings)
