from __future__ import division
from rdflib import URIRef
import sys
import time
import usb.core
import logging
from twisted.internet import task, threads, reactor
from greplin import scales
log = logging.getLogger('output')

# eliminate this: lists are always padded now
def setListElem(outList, index, value, fill=0, combine=lambda old, new: new):
    if len(outList) < index:
        outList.extend([fill] * (index - len(outList)))
    if len(outList) <= index:
        outList.append(value)
    else:
        outList[index] = combine(outList[index], value)

class Output(object):
    """
    send an array of values to some output device. Call update as
    often as you want- the result will be sent as soon as possible,
    and with repeats as needed to outlast hardware timeouts.
    """
    uri = None  # type: URIRef
    numChannels = None  # type: int
    def __init__(self):
        raise NotImplementedError
        
    def allConnections(self):
        """
        sequence of (index, uri) for the uris we can output, and which
        index in 'values' to use for them
        """
        raise NotImplementedError

    
    def update(self, values):
        """
        output takes a flattened list of values, maybe dmx channels, or
        pin numbers, etc
        """
        raise NotImplementedError

    def flush(self):
        """
        send latest data to output
        """
        raise NotImplementedError

    def shortId(self):
        """short string to distinguish outputs"""
        raise NotImplementedError

class DmxOutput(Output):
    def __init__(self, uri, numChannels):
        self.uri = uri
        self.numChannels = numChannels

    def flush(self):
        pass

    def _loop(self):
        start = time.time()
        sendingBuffer = self.currentBuffer

        def done(worked):
            if not worked:
                self.countError()
            else:
                self.lastSentBuffer = sendingBuffer
            reactor.callLater(max(0, start + 0.050 - time.time()),
                              self._loop)

        d = threads.deferToThread(self.sendDmx, sendingBuffer)
        d.addCallback(done)

class EnttecDmx(DmxOutput):
    stats = scales.collection('/output/enttecDmx',
                              scales.PmfStat('write'),
                              scales.PmfStat('update'))

    def __init__(self, uri, devicePath='/dev/dmx0', numChannels=80):
        DmxOutput.__init__(self, uri, numChannels)

        sys.path.append("dmx_usb_module")
        from dmx import Dmx
        self.dev = Dmx(devicePath)
        self.currentBuffer = ''
        self.lastLog = 0
        self._loop()

    @stats.update.time()
    def update(self, values):
        now = time.time()
        if now > self.lastLog + 1:
            log.info('enttec %s', ' '.join(map(str, values)))
            self.lastLog = now

        # I was outputting on 76 and it was turning on the light at
        # dmx75. So I added the 0 byte. No notes explaining the footer byte.
        self.currentBuffer = '\x00' + ''.join(map(chr, values)) + "\x00"

    @stats.write.time()
    def sendDmx(self, buf):
        self.dev.write(self.currentBuffer)

    def countError(self):
        pass

    def shortId(self):
        return 'enttec'

                                  
class Udmx(DmxOutput):
    stats = scales.collection('/output/udmx',
                              scales.PmfStat('update'),
                              scales.PmfStat('write'),
                              scales.IntStat('usbErrors'))
    def __init__(self, uri, numChannels):
        DmxOutput.__init__(self, uri, numChannels)
        
        from light9.io.udmx import Udmx
        self.dev = Udmx()
        self.currentBuffer = ''
        self.lastSentBuffer = None
        self.lastLog = 0

        # Doesn't actually need to get called repeatedly, but we do
        # need these two things:
        #   1. A throttle so we don't lag behind sending old updates.
        #   2. Retries if there are usb errors.
        # Copying the LoopingCall logic accomplishes those with a
        # little wasted time if there are no updates.
        #task.LoopingCall(self._loop).start(0.050)
        self._loop()

    @stats.update.time()
    def update(self, values):
        now = time.time()
        if now > self.lastLog + 1:
            log.info('udmx %s', ' '.join(map(str, values)))
            self.lastLog = now

        self.currentBuffer = ''.join(map(chr, values))

    def sendDmx(self, buf):
        with Udmx.stats.write.time():
            try:
                self.dev.SendDMX(buf)
                return True
            except usb.core.USBError:
                # not in main thread
                return False

    def countError(self):
        # in main thread
        Udmx.stats.usbErrors += 1
        
    def shortId(self):
        return 'udmx' # and something unique from self.dev?

