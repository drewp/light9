from __future__ import division
import time, json, logging, traceback
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from rdflib import URIRef, Literal
import cyclone.httpclient
from light9.namespaces import L9, RDF, RDFS
from light9.effecteval.effect import EffectNode
from light9 import networking
from light9 import Submaster
from light9 import dmxclient
log = logging.getLogger('effectloop')

class EffectLoop(object):
    """maintains a collection of the current EffectNodes, gets time from
    music player, sends dmx"""
    def __init__(self, graph, stats):
        self.graph, self.stats = graph, stats
        self.currentSong = None
        self.currentEffects = []
        self.lastLogTime = 0
        self.lastLogMsg = ""
        self.lastErrorLog = 0
        self.graph.addHandler(self.setEffects)
        self.period = 1 / 30
        self.coastSecs = .3 # main reason to keep this low is to notice play/pause

        self.songTimeFromRequest = 0
        self.requestTime = 0 # unix sec for when we fetched songTime
        reactor.callLater(self.period, self.sendLevels)

    def setEffects(self):
        self.currentEffects = []
        if self.currentSong is None:
            return
        
        for effectUri in self.graph.objects(self.currentSong, L9['effect']):
            self.currentEffects.append(EffectNode(self.graph, effectUri))
        
    @inlineCallbacks
    def getSongTime(self):
        now = time.time()
        if now - self.requestTime < self.coastSecs:
            estimated = self.songTimeFromRequest
            if self.currentSong is not None and self.currentPlaying:
                estimated += now - self.requestTime
            returnValue((estimated, self.currentSong))
        else:
            response = json.loads((yield cyclone.httpclient.fetch(
                networking.musicPlayer.path('time'))).body)
            self.requestTime = now
            self.currentPlaying = response['playing']
            self.songTimeFromRequest = response['t']
            returnValue(
                (response['t'], (response['song'] and URIRef(response['song']))))
            
    @inlineCallbacks
    def sendLevels(self):
        t1 = time.time()
        try:
            with self.stats.sendLevels.time():
                with self.stats.getMusic.time():
                    songTime, song = yield self.getSongTime()

                if song != self.currentSong:
                    self.currentSong = song
                    # this may be piling on the handlers
                    self.graph.addHandler(self.setEffects)

                if song is None:
                    return

                outSubs = []
                for e in self.currentEffects:
                    try:
                        outSubs.append(e.eval(songTime))
                    except Exception as exc:
                        now = time.time()
                        if now > self.lastErrorLog + 5:
                            log.error("effect %s: %s" % (e.uri, exc))
                            self.lastErrorLog = now
                out = Submaster.sub_maxes(*outSubs)

                self.logLevels(t1, out)
                dmx = out.get_dmx_list()
                with self.stats.writeDmx.time():
                    yield dmxclient.outputlevels(dmx, twisted=True)

                elapsed = time.time() - t1
                dt = max(0, self.period - elapsed)
        except Exception:
            self.stats.errors += 1
            traceback.print_exc()
            dt = 1

        reactor.callLater(dt, self.sendLevels)
        
    def logLevels(self, now, out):
        # this would look nice on the top of the effecteval web pages too
        if log.isEnabledFor(logging.DEBUG):
            log.debug(self.logMessage(out))
        else:
            if now > self.lastLogTime + 5:
                msg = self.logMessage(out)
                if msg != self.lastLogMsg:
                    log.info(msg)
                    self.lastLogMsg = msg
                self.lastLogTime = now
                
    def logMessage(self, out):
        return ("send dmx: {%s}" %
                ", ".join("%r: %.3g" % (str(k), v)
                          for k,v in out.get_levels().items()))
        
