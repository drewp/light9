#!/usr/bin/python

import math
import twisted.internet.fdesc
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from typing import Dict


class BCF2000(object):

    control = {81 : "slider1", 82 : "slider2", 83 : "slider3", 84 : "slider4",
               85 : "slider5", 86 : "slider6", 87 : "slider7", 88 : "slider8",
 
                1 : "knob1",  2 : "knob2",  3 : "knob3",  4 : "knob4",
                5 : "knob5",  6 : "knob6",  7 : "knob7",  8 : "knob8",

               33 : "button-knob1", 34 : "button-knob2",
               35 : "button-knob3", 36 : "button-knob4",
               37 : "button-knob5", 38 : "button-knob6",
               39 : "button-knob7", 40 : "button-knob8",
               
               65 : "button-upper1",  66 : "button-upper2",
               67 : "button-upper3",  68 : "button-upper4",
               69 : "button-upper5",  70 : "button-upper6",
               71 : "button-upper7",  72 : "button-upper8",
               73 : "button-lower1",  74 : "button-lower2",
               75 : "button-lower3",  76 : "button-lower4",
               77 : "button-lower5",  78 : "button-lower6",
               79 : "button-lower7",  80 : "button-lower8",
               89 : "button-corner1", 90 : "button-corner2",
               91 : "button-corner3", 92 : "button-corner4",
               }

    def __init__(self, dev="/dev/snd/midiC2D0"):
        """device was usually /dev/snd/midiC1D0 but then it showed up
        once as C0D0. It should be autodetected"""
        self.devPath = dev
        self.dev = None
        self.lastValue: Dict[str, int] = {}  # control name : value
        self.reopen()
        self.packet = b""
        loop = LoopingCall(self.poll)
        loop.start(.01)

    def poll(self):
        try:
            newData = self.dev.read(3)
        except (IOError, AttributeError):
            return
        if newData is None:
            return
        self.packet += newData
        if len(self.packet) == 3:
            p = self.packet
            self.packet = b""
            self.packetReceived(p)

    def packetReceived(self, packet):
        b0, which, value = packet
        if b0 != 0xb0:
            return
        if which in self.control:
            name = self.control[which]
            if name.startswith("button-"):
                value = value > 0
            self.lastValue[name] = value
            self.valueIn(name, value)
        else:
            print("unknown control %s to %s" % (which, value))

    def reopen(self):
        if self.dev is not None:
            try:
                self.dev.close()
            except IOError:
                pass

        self.lastValue.clear()
        self.dev = open(self.devPath, "rb+", buffering=0)
        twisted.internet.fdesc.setNonBlocking(self.dev)

    def valueIn(self, name, value):
        """override this with your handler for when events come in
        from the hardware"""
        print("slider %s to %s" % (name, value))
        if name == 'slider1':
            for x in range(2, 8 + 1):
                v2 = int(64 + 64 * math.sin(x / 3 + value / 10))
                self.valueOut('slider%d' % x, v2)
            for x in range(1, 8 + 1):
                self.valueOut('button-upper%s' % x, value > x * 15)
                self.valueOut('button-lower%s' % x, value > (x * 15 + 7))

    def valueOut(self, name, value):
        """call this to send an event to the hardware"""
        if self.dev is None:
            return

        value = int(value)
        if self.lastValue.get(name) == value:
            return
        self.lastValue[name] = value
        which = [k for k, v in list(self.control.items()) if v == name]
        assert len(which) == 1, "unknown control name %r" % name
        if name.startswith('button-'):
            value = value * 127
        #print "bcf: write %s %s" % (name, value)
        self.dev.write(bytes([0xb0, which[0], int(value)]))

    def close(self):
        self.dev.close()
        self.dev = None


if __name__ == '__main__':
    b = BCF2000()
    reactor.run()
