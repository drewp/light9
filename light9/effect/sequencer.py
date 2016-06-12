'''
copies from effectloop.py, which this should replace
'''

from __future__ import division
from rdflib import URIRef, Literal
from twisted.internet import reactor
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

log = logging.getLogger('sequencer')
stats = scales.collection('/sequencer/',
                                       scales.PmfStat('update'),
                          scales.DoubleStat('recentFps'),

                                       )
def sendToCollector(client, session, settings):
    return treq.put(networking.collector.path('attrs'),
                    data=json.dumps({'settings': settings,
                                     'client': client,
                                     'clientSession': session}))


class Note(object):
    def __init__(self, graph, uri, effectevalModule):
        g = self.graph = graph
        self.uri = uri
        self.effectEval = effectevalModule.EffectEval(
            graph, g.value(uri, L9['effectClass']))
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
        effectSettings = [(L9['strength'], self.evalCurve(t))]
        return self.effectEval.outputFromEffect(effectSettings, t)


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
        self.notes = {} # song: [notes]
        self.graph.addHandler(self.compileGraph)
        self.update()

        self.codeWatcher = CodeWatcher(
            onChange=lambda: self.graph.addHandler(self.compileGraph))

    def compileGraph(self):
        """rebuild our data from the graph"""
        g = self.graph

        for song in g.subjects(RDF.type, L9['Song']):
            self.notes[song] = []
            for note in g.objects(song, L9['note']):
                self.notes[song].append(Note(g, note, effecteval))

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
            # we have to send zeros to make past settings go
            # away. might be better for collector not to merge our
            # past requests, and then we can omit zeroed notes?
            outs = note.outputSettings(t)
            #print 'out', outs
            settings.extend(outs)
        self.sendToCollector(settings)
