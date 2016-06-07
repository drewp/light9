'''
copies from effectloop.py, which this should replace
'''

from __future__ import division
from rdflib import URIRef, Literal
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, succeed
from webcolors import hex_to_rgb, rgb_to_hex
import time, json, logging, traceback, bisect

from light9.namespaces import L9, RDF, RDFS
from light9.vidref.musictime import MusicTime

log = logging.getLogger('sequencer')

class Note(object):
    def __init__(self, graph, uri):
        g = self.graph = graph
        self.uri = uri
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

        for ds in g.objects(g.value(uri, L9['effectClass']), L9['deviceSetting']):
            self.setting = (g.value(ds, L9['device']), g.value(ds, L9['attr']))
        
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

        c = int(255 * self.evalCurve(t))
        color = [0, 0, 0]
        if self.setting[1] == L9['red']: # throwaway
            color[0] = c
        elif self.setting[1] == L9['blue']:
            color[2] = c
        
        return [
            # device, attr, lev
            (self.setting[0],
             URIRef("http://light9.bigasterisk.com/color"),
             Literal(rgb_to_hex(color)))
            ]
            
class Sequencer(object):
    def __init__(self, graph, sendToCollector):
        self.graph = graph
        self.sendToCollector = sendToCollector
        self.music = MusicTime(period=.2, pollCurvecalc=False)

        self.notes = {} # song: [notes]
        self.graph.addHandler(self.compileGraph)
        self.update()

    def compileGraph(self):
        """rebuild our data from the graph"""
        g = self.graph
        for song in g.subjects(RDF.type, L9['Song']):
            self.notes[song] = []
            for note in g.objects(song, L9['note']):
                self.notes[song].append(Note(g, note))
        
    def update(self):
        reactor.callLater(1/30, self.update)

        musicState = self.music.getLatest()
        song = URIRef(musicState['song']) if 'song' in musicState else None
        if 't' not in musicState:
            return
        t = musicState['t']

        settings = []
        
        for note in self.notes.get(song, []):
            # we have to send zeros to make past settings go
            # away. might be better for collector not to merge our
            # past requests, and then we can omit zeroed notes?
            settings.extend(note.outputSettings(t))
        self.sendToCollector(settings)
