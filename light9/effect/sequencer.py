'''
copies from effectloop.py, which this should replace
'''

from louie import dispatcher
from rdflib import URIRef
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.inotify import INotify
from twisted.python.filepath import FilePath
import cyclone.sse
import logging, bisect, time
import traceback
from decimal import Decimal
from typing import Any, Callable, Dict, List, Tuple, cast, Union

from light9.ascoltami.musictime_client import MusicTime
from light9.effect import effecteval
from light9.effect.settings import DeviceSettings
from light9.effect.simple_outputs import SimpleOutputs
from light9.namespaces import L9, RDF
from light9.newtypes import DeviceUri, DeviceAttr, NoteUri, Curve, Song
from rdfdb.syncedgraph import SyncedGraph
from standardservice.scalessetup import gatherProcessStats

from greplin import scales
import imp

log = logging.getLogger('sequencer')

gatherProcessStats()
updateStats = scales.collection(
    '/update',
    scales.PmfStat('s0_getMusic', recalcPeriod=1),
    scales.PmfStat('s1_eval', recalcPeriod=1),
    #scales.PmfStat('s3_send_client', recalcPeriod=1),
    scales.PmfStat('s3_send', recalcPeriod=1),
    scales.PmfStat('updateLoopLatency', recalcPeriod=1),
    scales.DoubleStat('updateLoopLatencyGoal'),
    scales.RecentFpsStat('updateFps'),
    scales.DoubleStat('goalFps'),
)
compileStats = scales.collection(
    '/compile',
    scales.PmfStat('graph', recalcPeriod=1),
    scales.PmfStat('song', recalcPeriod=1),
)


def pyType(n):
    ret = n.toPython()
    if isinstance(ret, Decimal):
        return float(ret)
    return ret


class Note(object):

    def __init__(self, graph: SyncedGraph, uri: NoteUri, effectevalModule,
                 simpleOutputs):
        g = self.graph = graph
        self.uri = uri
        self.effectEval = effectevalModule.EffectEval(
            graph, g.value(uri, L9['effectClass']), simpleOutputs)
        self.baseEffectSettings: Dict[URIRef, Any] = {}  # {effectAttr: value}
        for s in g.objects(uri, L9['setting']):
            settingValues = dict(g.predicate_objects(s))
            ea = settingValues[L9['effectAttr']]
            self.baseEffectSettings[ea] = pyType(settingValues[L9['value']])

        def floatVal(s, p):
            return float(g.value(s, p).toPython())

        originTime = floatVal(uri, L9['originTime'])
        self.points: List[Tuple[float, float]] = []
        for curve in g.objects(uri, L9['curve']):
            self.points.extend(
                self.getCurvePoints(curve, L9['strength'], originTime))
        self.points.sort()

    def getCurvePoints(self, curve: Curve, attr,
                       originTime: float) -> List[Tuple[float, float]]:
        points = []
        po = list(self.graph.predicate_objects(curve))
        if dict(po).get(L9['attr'], None) != attr:
            return []
        for point in [row[1] for row in po if row[0] == L9['point']]:
            po2 = dict(self.graph.predicate_objects(point))
            points.append(
                (originTime + float(po2[L9['time']]), float(po2[L9['value']])))
        return points

    def activeAt(self, t: float) -> bool:
        return self.points[0][0] <= t <= self.points[-1][0]

    def evalCurve(self, t: float) -> float:
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

    def outputSettings(
            self,
            t: float) -> Tuple[List[Tuple[DeviceUri, DeviceAttr, float]], Dict]:
        """
        list of (device, attr, value), and a report for web
        """
        report = {
            'note': str(self.uri),
            'effectClass': self.effectEval.effect,
        }
        effectSettings: Dict[DeviceAttr, Union[float, str]] = dict(
            (DeviceAttr(da), v) for da, v in self.baseEffectSettings.items())
        effectSettings[L9['strength']] = self.evalCurve(t)

        def prettyFormat(x: Union[float, str]):
            if isinstance(x, float):
                return round(x, 4)
            return x

        report['effectSettings'] = dict(
            (str(k), prettyFormat(v))
            for k, v in sorted(effectSettings.items()))
        report['nonZero'] = cast(float, effectSettings[L9['strength']]) > 0
        out, evalReport = self.effectEval.outputFromEffect(
            list(effectSettings.items()),
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
        self.notifier.watch(FilePath(effecteval.__file__.replace('.pyc',
                                                                 '.py')),
                            callbacks=[self.codeChange])

    def codeChange(self, watch, path, mask):

        def go():
            log.info("reload effecteval")
            imp.reload(effecteval)
            self.onChange()

        # in case we got an event at the start of the write
        reactor.callLater(.1, go)


class Sequencer(object):

    def __init__(self,
                 graph: SyncedGraph,
                 sendToCollector: Callable[[DeviceSettings], Deferred],
                 fps=40):
        self.graph = graph
        self.fps = fps
        updateStats.goalFps = self.fps
        updateStats.updateLoopLatencyGoal = 1 / self.fps
        self.sendToCollector = sendToCollector
        self.music = MusicTime(period=.2, pollCurvecalc=False)

        self.recentUpdateTimes: List[float] = []
        self.lastStatLog = 0.0
        self._compileGraphCall = None
        self.notes: Dict[Song, List[Note]] = {}  # song: [notes]
        self.simpleOutputs = SimpleOutputs(self.graph)
        self.graph.addHandler(self.compileGraph)
        self.lastLoopSucceeded = False

        self.codeWatcher = CodeWatcher(onChange=self.onCodeChange)
        self.updateLoop()

    def onCodeChange(self):
        log.debug('seq.onCodeChange')
        self.graph.addHandler(self.compileGraph)
        #self.updateLoop()

    @compileStats.graph.time()
    def compileGraph(self) -> None:
        """rebuild our data from the graph"""
        for song in self.graph.subjects(RDF.type, L9['Song']):

            def compileSong(song: Song = cast(Song, song)) -> None:
                self.compileSong(song)

            self.graph.addHandler(compileSong)

    @compileStats.song.time()
    def compileSong(self, song: Song) -> None:
        anyErrors = False
        self.notes[song] = []
        for note in self.graph.objects(song, L9['note']):
            try:
                n = Note(self.graph, NoteUri(note), effecteval,
                         self.simpleOutputs)
            except Exception:
                log.warn(f"failed to build Note {note} - skipping")
                anyErrors = True
                continue
            self.notes[song].append(n)
        if not anyErrors:
            log.info('built all notes')

    @inlineCallbacks
    def updateLoop(self) -> None:
        frameStart = time.time()
        try:
            sec = yield self.update()
        except Exception as e:
            self.lastLoopSucceeded = False
            traceback.print_exc()
            log.warn('updateLoop: %r', e)
            reactor.callLater(1, self.updateLoop)
        else:
            took = time.time() - frameStart
            updateStats.updateLoopLatency = took

            if not self.lastLoopSucceeded:
                log.info('Sequencer.update is working')
                self.lastLoopSucceeded = True

            delay = max(0, 1 / self.fps - took)
            reactor.callLater(delay, self.updateLoop)

    @updateStats.updateFps.rate()
    @inlineCallbacks
    def update(self) -> Deferred:

        with updateStats.s0_getMusic.time():
            musicState = self.music.getLatest()
            if not musicState.get('song') or not isinstance(
                    musicState.get('t'), float):
                return defer.succeed(0.0)
            song = Song(URIRef(musicState['song']))
            dispatcher.send('state',
                            update={
                                'song': str(song),
                                't': musicState['t']
                            })

        with updateStats.s1_eval.time():
            settings = []
            songNotes = sorted(self.notes.get(song, []), key=lambda n: n.uri)
            noteReports = []
            for note in songNotes:
                try:
                    s, report = note.outputSettings(musicState['t'])
                except Exception:
                    traceback.print_exc()
                    raise
                noteReports.append(report)
                settings.append(s)
            devSettings = DeviceSettings.fromList(self.graph, settings)

        dispatcher.send('state', update={'songNotes': noteReports})

        with updateStats.s3_send.time():  # our measurement
            sendSecs = yield self.sendToCollector(devSettings)

        # sendToCollector's own measurement.
        # (sometimes it's None, not sure why, and neither is mypy)
        #if isinstance(sendSecs, float):
        #    updateStats.s3_send_client = sendSecs


class Updates(cyclone.sse.SSEHandler):

    def __init__(self, application, request, **kwargs) -> None:
        cyclone.sse.SSEHandler.__init__(self, application, request, **kwargs)
        self.state: Dict = {}
        dispatcher.connect(self.updateState, 'state')
        self.numConnected = 0

    def updateState(self, update: Dict):
        self.state.update(update)

    def bind(self) -> None:
        self.numConnected += 1

        if self.numConnected == 1:
            self.loop()

    def loop(self) -> None:
        if self.numConnected == 0:
            return
        self.sendEvent(self.state)
        reactor.callLater(.1, self.loop)

    def unbind(self) -> None:
        self.numConnected -= 1
