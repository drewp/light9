from __future__ import division
from rdflib import URIRef
import sys
import time
import usb.core
import logging
from twisted.internet import task
from greplin import scales
log = logging.getLogger('output')

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


class DmxOutput(Output):
    def __init__(self, uri):
        self.uri = uri

    def flush(self):
        pass


class EnttecDmx(DmxOutput):
    stats = scales.collection('/output/enttecDmx',
                              scales.PmfStat('write'),
                              scales.PmfStat('update'))

    def __init__(self, uri, devicePath='/dev/dmx0'):
        DmxOutput.__init__(self, uri)

        sys.path.append("dmx_usb_module")
        from dmx import Dmx
        self.dev = Dmx(devicePath)
        self.currentBuffer = ''
        self.lastLog = 0
        task.LoopingCall(self._loop).start(0.050)

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
    def _loop(self):
        self.dev.write(self.currentBuffer)

class Udmx(DmxOutput):
    stats = scales.collection('/output/udmx',
                              scales.PmfStat('update'),
                              scales.PmfStat('write'),
                              scales.IntStat('usbErrors'))
    def __init__(self, uri):
        DmxOutput.__init__(self, uri)
        
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
        task.LoopingCall(self._loop).start(0.050)

    @stats.update.time()
    def update(self, values):
        now = time.time()
        if now > self.lastLog + 1:
            log.info('udmx %s', ' '.join(map(str, values)))
            self.lastLog = now

        self.currentBuffer = ''.join(map(chr, values))
    
    def _loop(self):
        #if self.lastSentBuffer == self.currentBuffer:
        #    return
        with Udmx.stats.write.time():
            # frequently errors with usb.core.USBError
            try:
                self.dev.SendDMX(self.currentBuffer)
                self.lastSentBuffer = self.currentBuffer
            except usb.core.USBError:
                Udmx.stats.usbErrors += 1

