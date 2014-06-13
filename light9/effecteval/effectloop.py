from __future__ import division
import time, json, logging, traceback
import numpy
import serial
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, succeed
from rdflib import URIRef, Literal
import cyclone.httpclient
from light9.namespaces import L9, RDF, RDFS
from light9.effecteval.effect import EffectNode
from light9 import Effects
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
        self.initOutput()

    def initOutput(self):
        pass

    def startLoop(self):
        log.info("startLoop")
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

                outputs = self.allEffectOutputs(songTime)
                combined = self.combineOutputs(outputs)
                self.logLevels(t1, combined)
                yield self.sendOutput(combined)
                
                elapsed = time.time() - t1
                dt = max(0, self.period - elapsed)
        except Exception:
            self.stats.errors += 1
            traceback.print_exc()
            dt = 1

        reactor.callLater(dt, self.sendLevels)

    def combineOutputs(self, outputs):
        """pick usable effect outputs and reduce them into one for sendOutput"""
        outputs = [x for x in outputs if isinstance(x, Submaster.Submaster)]
        log.info('outputs %r', outputs)
        out = Submaster.sub_maxes(*outputs)

        return out
        
    @inlineCallbacks
    def sendOutput(self, combined):
        dmx = combined.get_dmx_list()
        with self.stats.writeDmx.time():
            yield dmxclient.outputlevels(dmx, twisted=True)
        
    def allEffectOutputs(self, songTime):
        outputs = []
        for e in self.currentEffects:
            try:
                outputs.append(e.eval(songTime))
            except Exception as exc:
                now = time.time()
                if now > self.lastErrorLog + 5:
                    log.error("effect %s: %s" % (e.uri, exc))
                    self.lastErrorLog = now
        return outputs
        
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

Z = numpy.zeros((50, 3), dtype=numpy.uint8)

class LedLoop(EffectLoop):
    def initOutput(self):
        kw = dict(baudrate=115200)
        self.boards = {
            'L': serial.Serial('/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A7027NYX-if00-port0', **kw),
            'R': serial.Serial('/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A7027JI6-if00-port0', **kw),
        }
        
    def combineOutputs(self, outputs):
        combined = {'L': Z, 'R': Z, 'blacklight': 0}
        
        for out in outputs:
            if isinstance(out, Effects.Blacklight):
                combined['blacklight'] = max(combined['blacklight'], int(out * 255))
            elif isinstance(out, Effects.ColorStrip):
                pixels = numpy.array(out.pixels, dtype=numpy.float16)
                px255 = (numpy.clip(pixels, 0, 1) * 255).astype(numpy.uint8)
                combined[out.which] = numpy.maximum(combined[out.which], px255)
                
        return combined
                
    def sendOutput(self, combined):
        for which, px255 in combined.items():
            if which == 'blacklight':
                self.boards['L'].write('\x60\x01' + chr(px255))
                self.boards['L'].flush()
            else:
                board = self.boards[which]
                msg = '\x60\x00' + px255.reshape((-1,)).tostring()
                board.write(msg)
                board.flush()
                
        return succeed(None)
        
    def logMessage(self, out):
        return str([(w, p.tolist() if isinstance(p, numpy.ndarray) else p) for w,p in out.items()])

def makeEffectLoop(graph, stats, outputWhere):
    if outputWhere == 'dmx':
        return EffectLoop(graph, stats)
    elif outputWhere == 'leds':
        return LedLoop(graph, stats)
    else:
        raise NotImplementedError

        
