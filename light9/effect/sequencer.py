'''
copies from effectloop.py, which this should replace
'''

from __future__ import division
from louie import dispatcher
from rdflib import URIRef
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet.inotify import INotify
from twisted.python.filepath import FilePath
import cyclone.sse
import logging, bisect, time
import traceback

from light9.namespaces import L9, RDF
from light9.vidref.musictime import MusicTime
from light9.effect import effecteval
from light9.effect.settings import DeviceSettings
from light9.effect.simple_outputs import SimpleOutputs

from greplin import scales

log = logging.getLogger('sequencer')
stats = scales.collection('/sequencer/',
                          scales.PmfStat('update'),
                          scales.PmfStat('compileGraph'),
                          scales.PmfStat('compileSong'),
                          scales.DoubleStat('recentFps'),
)


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
        report = {'note': str(self.uri),
                  'effectClass': self.effectEval.effect,
        }
        effectSettings = self.baseEffectSettings.copy()
        effectSettings[L9['strength']] = self.evalCurve(t)
        report['effectSettings'] = dict(
            (str(k), str(v))
            for k,v in sorted(effectSettings.items()))
        report['nonZero'] = effectSettings[L9['strength']] > 0
        out, evalReport = self.effectEval.outputFromEffect(
            effectSettings.items(),
            songTime=t,
            # note: not using origin here since it's going away
            noteTime=t - self.points[0][0])
        report['devicesAffected'] = len(out.devices())
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
        self.updateLoop()

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


    def updateLoop(self):
        # print "updateLoop"
        now = time.time()
        self.recentUpdateTimes = self.recentUpdateTimes[-40:] + [now]
        stats.recentFps = len(self.recentUpdateTimes) / (self.recentUpdateTimes[-1] - self.recentUpdateTimes[0] + .0001)
        if now > self.lastStatLog + .2:
            dispatcher.send('state', update={
                'recentDeltas': sorted([round(t1 - t0, 4) for t0, t1 in
                                 zip(self.recentUpdateTimes[:-1],
                                     self.recentUpdateTimes[1:])]),
                'recentFps': stats.recentFps})
            self.lastStatLog = now

        def done(sec):
            # print "sec", sec
            # delay = max(0, time.time() - (now + 1 / self.fps))
            # print 'cl', delay
            delay = 0.005
            reactor.callLater(delay, self.updateLoop)
        def err(e):
            log.warn('updateLoop: %r', e)
            reactor.callLater(2, self.updateLoop)
            
        d = self.update()
        d.addCallbacks(done, err)
        
    @stats.update.time()
    def update(self):
        # print "update"
        try:
            musicState = self.music.getLatest()
            song = URIRef(musicState['song']) if musicState.get('song') else None
            if 't' not in musicState:
                return defer.succeed(0)
            t = musicState['t']
            dispatcher.send('state', update={'song': str(song), 't': t})

            settings = []
            songNotes = sorted(self.notes.get(song, []), key=lambda n: n.uri)
            noteReports = []
            for note in songNotes:
                s, report = note.outputSettings(t)
                noteReports.append(report)
                settings.append(s)
            dispatcher.send('state', update={'songNotes': noteReports})
            return self.sendToCollector(DeviceSettings.fromList(self.graph, settings))
        except Exception:
            traceback.print_exc()
            raise

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
        self.numConnected += 1
        
        if self.numConnected == 1:
            self.loop()

    def loop(self):
        if self.numConnected == 0:
            return
        self.sendEvent(self.state)
        reactor.callLater(.1, self.loop)
        
    def unbind(self):
        self.numConnected -= 1

    
