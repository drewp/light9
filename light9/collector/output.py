from rdflib import URIRef
import time
import usb.core
import logging
from twisted.internet import threads, reactor, task
from greplin import scales
log = logging.getLogger('output')
logAllDmx = logging.getLogger('output.allDmx')


class Output(object):
    """
    send a binary buffer of values to some output device. Call update
    as often as you want- the result will be sent as soon as possible,
    and with repeats as needed to outlast hardware timeouts.

    This base class doesn't ever call _write. Subclasses below have
    strategies for that.
    """
    uri: URIRef

    def __init__(self, uri: URIRef):
        self.uri = uri
        scales.init(self, '/output%s' % self.shortId())
        self._currentBuffer = b''

        if log.isEnabledFor(logging.DEBUG):
            self._lastLoggedMsg = ''
            task.LoopingCall(self._periodicLog).start(1)

    def shortId(self) -> str:
        """short string to distinguish outputs"""
        return self.uri.rstrip('/').rsplit('/')[-1]

    def update(self, buf: bytes) -> None:
        """caller asks for the output to be this buffer"""
        self._currentBuffer = buf

    def _periodicLog(self):
        msg = '%s: %s' % (self.shortId(), ' '.join(map(str,
                                                       self._currentBuffer)))
        if msg != self._lastLoggedMsg:
            log.debug(msg)
            self._lastLoggedMsg = msg

    _writeSucceed = scales.IntStat('write/succeed')
    _writeFail = scales.IntStat('write/fail')
    _writeCall = scales.PmfStat('write/call')
    _writeFps = scales.RecentFpsStat('write/fps')
    def _write(self, buf: bytes) -> None:
        """
        write buffer to output hardware (may be throttled if updates are
        too fast, or repeated if they are too slow)
        """
        pass


class DummyOutput(Output):

    def __init__(self, uri, **kw):
        super().__init__(uri)


class BackgroundLoopOutput(Output):
    """Call _write forever at 20hz in background threads"""

    rate = 30  # Hz

    def __init__(self, uri):
        super().__init__(uri)
        self._currentBuffer = b''

        self._loop()

    def _loop(self):
        start = time.time()
        sendingBuffer = self._currentBuffer

        def done(worked):
            self._writeSucceed += 1
            reactor.callLater(max(0, start + 1 / self.rate - time.time()),
                              self._loop)

        def err(e):
            self._writeFail += 1
            log.error(e)

        d = threads.deferToThread(self._write, sendingBuffer)
        d.addCallbacks(done, err)


class Udmx(BackgroundLoopOutput):

    def __init__(self, uri, bus, address, lastDmxChannel):
        self.lastDmxChannel = lastDmxChannel
        from pyudmx import pyudmx
        self.dev = pyudmx.uDMXDevice()
        if not self.dev.open(bus=bus, address=address):
            raise ValueError("dmx open failed")

        super().__init__(uri)

    _writeOverflow = scales.IntStat('write/overflow')

    #def update(self, buf:bytes):
    #    self._write(buf)

    #def _loop(self):
    #    pass
    def _write(self, buf):
        self._writeFps.mark()
        with self._writeCall.time():
            try:
                if not buf:
                    return

                # ok to truncate the last channels if they just went
                # to 0? No it is not. DMX receivers don't add implicit
                # zeros there.
                buf = buf[:self.lastDmxChannel]

                if logAllDmx.isEnabledFor(logging.DEBUG):
                    # for testing fps, smooth fades, etc
                    logAllDmx.debug(
                        '%s: %s' %
                        (self.shortId(), ' '.join(map(str, buf[:16]))))

                sent = self.dev.send_multi_value(1, buf)
                if sent != len(buf):
                    raise ValueError("incomplete send")

            except usb.core.USBError as e:
                # not in main thread
                if e.errno == 75:
                    self._writeOverflow += 1
                    return

                msg = 'usb: sending %s bytes to %r; error %r' % (len(buf),
                                                                 self.uri, e)
                log.warn(msg)
                raise


'''
# the code used in 2018 and before
class UdmxOld(BackgroundLoopOutput):
    
    def __init__(self, uri, bus):
        from light9.io.udmx import Udmx
        self._dev = Udmx(bus)
        
        super().__init__(uri)

    def _write(self, buf: bytes):
        try:
            if not buf:
                return
            self.dev.SendDMX(buf)

        except usb.core.USBError as e:
            # not in main thread
            if e.errno != 75:
                msg = 'usb: sending %s bytes to %r; error %r' % (
                    len(buf), self.uri, e)
                log.warn(msg)
            raise
          
                                
# out of date
class EnttecDmx(BackgroundLoopOutput):
    stats = scales.collection('/output/enttecDmx', scales.PmfStat('write'),
                              scales.PmfStat('update'))

    def __init__(self, uri, devicePath='/dev/dmx0', numChannels=80):
        sys.path.append("dmx_usb_module")
        from dmx import Dmx
        self.dev = Dmx(devicePath)
        super().__init__(uri)


    @stats.update.time()
    def update(self, values):

        # I was outputting on 76 and it was turning on the light at
        # dmx75. So I added the 0 byte. No notes explaining the footer byte.
        self.currentBuffer = '\x00' + ''.join(map(chr, values)) + "\x00"

    @stats.write.time()
    def _write(self, buf):
        self.dev.write(buf)
'''
