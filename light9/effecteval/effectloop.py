from __future__ import division
import time, json, logging, traceback
import numpy
import serial
from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks, returnValue, succeed
from twisted.internet.error import TimeoutError
from rdflib import URIRef, Literal
import cyclone.httpclient
from light9.namespaces import L9, RDF, RDFS
from light9.effecteval.effect import EffectNode
from light9 import Effects
from light9 import networking
from light9 import Submaster
from light9 import dmxclient
from light9 import prof
log = logging.getLogger('effectloop')

class EffectLoop(object):
    """maintains a collection of the current EffectNodes, gets time from
    music player, sends dmx"""
    def __init__(self, graph, stats):
        self.graph, self.stats = graph, stats
        self.currentSong = None
        self.currentEffects = [] # EffectNodes for the current song plus the submaster ones
        self.lastLogTime = 0
        self.lastLogMsg = ""
        self.lastErrorLog = 0
        self.graph.addHandler(self.setEffects)
        self.period = 1 / 30
        self.coastSecs = .3 # main reason to keep this low is to notice play/pause
        self.songTimeFetch = 0
        self.songIsPlaying = False
        self.songTimeFromRequest = 0
        self.requestTime = 0 # unix sec for when we fetched songTime
        self.initOutput()

    def initOutput(self):
        pass

    def startLoop(self):
        log.info("startLoop")
        self.lastSendLevelsTime = 0
        reactor.callLater(self.period, self.sendLevels)
        reactor.callLater(self.period, self.updateTimeFromMusic)

    def setEffects(self):
        self.currentEffects = []
        log.info('setEffects currentSong=%s', self.currentSong)
        if self.currentSong is None:
            return
        
        for effectUri in self.graph.objects(self.currentSong, L9['effect']):
            self.currentEffects.append(EffectNode(self.graph, effectUri))


        for sub in self.graph.subjects(RDF.type, L9['Submaster']):
            for effectUri in self.graph.objects(sub, L9['drivesEffect']):
                self.currentEffects.append(EffectNode(self.graph, effectUri))
                
        log.info('now we have %s effects', len(self.currentEffects))
        
    @inlineCallbacks
    def getSongTime(self):
        now = time.time()
        old = now - self.requestTime
        if old > self.coastSecs:
            try:
                response = json.loads((yield cyclone.httpclient.fetch(
                    networking.musicPlayer.path('time'), timeout=.5)).body)
            except TimeoutError:
                log.warning("TimeoutError: using stale time from %.1f ago", old)
            else:
                self.requestTime = now
                self.currentPlaying = response['playing']
                self.songTimeFromRequest = response['t']
                returnValue(
                    (response['t'], (response['song'] and URIRef(response['song']))))

        estimated = self.songTimeFromRequest
        if self.currentSong is not None and self.currentPlaying:
            estimated += now - self.requestTime
        returnValue((estimated, self.currentSong))


    @inlineCallbacks
    def updateTimeFromMusic(self):
        t1 = time.time()
        with self.stats.getMusic.time():
            self.songTime, song = yield self.getSongTime()
            self.songTimeFetch = time.time()

        if song != self.currentSong:
            self.currentSong = song
            # this may be piling on the handlers
            self.graph.addHandler(self.setEffects)

        elapsed = time.time() - t1
        reactor.callLater(max(0, self.period - elapsed), self.updateTimeFromMusic)

    def estimatedSongTime(self):
        now = time.time()
        t = self.songTime
        if self.currentPlaying:
            t += max(0, now - self.songTimeFetch)
        return t

    @inlineCallbacks
    def sendLevels(self):
        print ''
        t1 = time.time()
        log.debug("time since last call: %.1f ms" % (1000 * (t1 - self.lastSendLevelsTime)))
        self.lastSendLevelsTime = t1
        try:
            with self.stats.sendLevels.time():
                if self.currentSong is not None:
                    log.debug('allEffectOutputs')
                    with self.stats.evals.time():
                        outputs = self.allEffectOutputs(self.estimatedSongTime())
                    log.debug('combineOutputs')
                    combined = self.combineOutputs(outputs)
                    self.logLevels(t1, combined)
                    log.debug('sendOutput')
                    with self.stats.sendOutput.time():
                        yield self.sendOutput(combined)
                
                elapsed = time.time() - t1
                dt = max(0, self.period - elapsed)
        except Exception:
            self.stats.errors += 1
            traceback.print_exc()
            dt = .5

        reactor.callLater(dt, self.sendLevels)

    def combineOutputs(self, outputs):
        """pick usable effect outputs and reduce them into one for sendOutput"""
        outputs = [x for x in outputs if isinstance(x, Submaster.Submaster)]
        out = Submaster.sub_maxes(*outputs)

        return out
        
    @inlineCallbacks
    def sendOutput(self, combined):
        dmx = combined.get_dmx_list()
        yield dmxclient.outputlevels(dmx, twisted=True)
        
    def allEffectOutputs(self, songTime):
        outputs = []
        for e in self.currentEffects:
            try:
                out = e.eval(songTime)
                if isinstance(out, (list, tuple)):
                    outputs.extend(out)
                else:
                    outputs.append(out)
            except Exception as exc:
                now = time.time()
                if now > self.lastErrorLog + 5:
                    if hasattr(exc, 'expr'):
                        log.exception('in expression %r', exc.expr)
                    log.error("effect %s: %s" % (e.uri, exc))
                    self.lastErrorLog = now
        log.debug('eval %s effects, got %s outputs', len(self.currentEffects), len(outputs))
                    
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

Z = numpy.zeros((50, 3), dtype=numpy.float16)

class ControlBoard(object):
    def __init__(self, dev='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A7027NYX-if00-port0'):
        self._dev = serial.Serial(dev, baudrate=115200)

    def _8bitMessage(self, floatArray):
        px255 = (numpy.clip(floatArray, 0, 1) * 255).astype(numpy.uint8)
        return px255.reshape((-1,)).tostring()
        
    def setStrip(self, which, pixels):
        """
        which: 0 or 1 to pick the strip
        pixels: (50, 3) array of 0..1 floats
        """
        command = {0: '\x00', 1: '\x01'}[which]
        if pixels.shape != (50, 3):
            raise ValueError("pixels was %s" % pixels.shape)
        self._dev.write('\x60' + command + self._8bitMessage(pixels))
        self._dev.flush()

    def setUv(self, which, level):
        """
        which: 0 or 1
        level: 0 to 1
        """
        command = {0: '\x02', 1: '\x03'}[which]
        self._dev.write('\x60' + command + chr(int(max(0, min(1, level)) * 255)))
        self._dev.flush()

    def setRgb(self, color):
        """
        color: (1, 3) array of 0..1 floats
        """
        if color.shape != (1, 3):
            raise ValueError("color was %s" % color.shape)
        self._dev.write('\x60\x04' + self._8bitMessage(color))
        self._dev.flush()

        
class LedLoop(EffectLoop):
    def initOutput(self):
        self.board = ControlBoard()
        self.lastSent = {} # what's in arduino's memory
        
    def combineOutputs(self, outputs):
        combined = {'L': Z, 'R': Z,
                    'blacklight0': 0, 'blacklight1': 0,
                    'W': numpy.zeros((1, 3), dtype=numpy.float16)}
        
        for out in outputs:
            log.debug('combine output %r', out)


            # workaround- somehow these subs that drive fx aren't
            # sending their fx, so we react to the sub
            if isinstance(out, Submaster.Submaster) and '*' in out.name:
                level = float(out.name.split('*')[1])
                n = out.name.split('*')[0]
                if n == 'widered': out = Effects.Strip.solid('W', (1,0,0)) * level
                if n == 'widegreen': out = Effects.Strip.solid('W', (0,1,0)) * level
                if n == 'wideblue': out = Effects.Strip.solid('W', (0,0,1)) * level
                if n == 'whiteled': out = Effects.Strip.solid('W', (1,.5,.5)) * level
 
            if isinstance(out, Effects.Blacklight):
                # no picking yet
                #key = 'blacklight%s' % out.which
                for key in ['blacklight0', 'blacklight1']:
                    combined[key] = max(combined[key], out)
            elif isinstance(out, Effects.Strip):
                pixels = numpy.array(out.pixels, dtype=numpy.float16)
                for w in out.which:
                    combined[w] = numpy.maximum(
                        combined[w], pixels[:1,:] if w == 'W' else pixels)
                
        return combined

    @inlineCallbacks
    def sendOutput(self, combined):
        for meth, selectArgs, value in [
                ('setStrip', (0,), combined['L']),
                ('setStrip', (1,), combined['R']),
                ('setUv', (0,), combined['blacklight0']),
                ('setUv', (1,), combined['blacklight1']),
                ('setRgb', (), combined['W']),
            ]:
            key = (meth, selectArgs)
            compValue = value.tolist() if isinstance(value, numpy.ndarray) else value
            
            if self.lastSent.get(key) == compValue:
                continue

            log.debug('value changed: %s(%s %s)', meth, selectArgs, value)
            
            getattr(self.board, meth)(*(selectArgs + (value,)))
            self.lastSent[key] = compValue
                
        yield succeed(None) # there was an attempt at an async send
        
    def logMessage(self, out):
        return str([(w, p.tolist() if isinstance(p, numpy.ndarray) else p) for w,p in out.items()])

def makeEffectLoop(graph, stats, outputWhere):
    if outputWhere == 'dmx':
        return EffectLoop(graph, stats)
    elif outputWhere == 'leds':
        return LedLoop(graph, stats)
    else:
        raise NotImplementedError("unknown output system %r" % outputWhere)

        
