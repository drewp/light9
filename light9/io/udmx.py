
import logging
import usb.core
from usb.util import CTRL_TYPE_VENDOR, CTRL_RECIPIENT_DEVICE, CTRL_OUT

log = logging.getLogger('udmx')
"""
Send dmx to one of these:
http://www.amazon.com/Interface-Adapter-Controller-Lighting-Freestyler/dp/B00W52VIOS

[4520784.059479] usb 1-2.3: new low-speed USB device number 6 using xhci_hcd
[4520784.157410] usb 1-2.3: New USB device found, idVendor=16c0, idProduct=05dc
[4520784.157416] usb 1-2.3: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[4520784.157419] usb 1-2.3: Product: uDMX
[4520784.157422] usb 1-2.3: Manufacturer: www.anyma.ch
[4520784.157424] usb 1-2.3: SerialNumber: ilLUTZminator001

See https://www.illutzmination.de/udmxfirmware.html?&L=1
    sources/commandline/uDMX.c
or https://github.com/markusb/uDMX-linux/blob/master/uDMX.c
"""

cmd_SetChannelRange = 0x0002


class Udmx(object):

    def __init__(self, bus):
        self.dev = None
        for dev in usb.core.find(idVendor=0x16c0,
                                 idProduct=0x05dc,
                                 find_all=True):
            print("udmx device at %r" % dev.bus)
            if bus is None or bus == dev.bus:
                self.dev = dev
        if not self.dev:
            raise IOError('no matching udmx device found for requested bus %r' %
                          bus)
        log.info('found udmx at %r', self.dev)

    def SendDMX(self, buf):
        ret = self.dev.ctrl_transfer(bmRequestType=CTRL_TYPE_VENDOR |
                                     CTRL_RECIPIENT_DEVICE | CTRL_OUT,
                                     bRequest=cmd_SetChannelRange,
                                     wValue=len(buf),
                                     wIndex=0,
                                     data_or_wLength=buf)
        if ret < 0:
            raise ValueError("ctrl_transfer returned %r" % ret)


def demo(chan, fps=44):
    import time, math
    u = Udmx()
    while True:
        nsin = math.sin(time.time() * 6.28) / 2.0 + 0.5
        nsin8 = int(255 * nsin)
        try:
            u.SendDMX('\x00' * (chan - 1) + chr(210) + chr(nsin8) + chr(nsin8) +
                      chr(nsin8))
        except usb.core.USBError as e:
            print("err", time.time(), repr(e))
        time.sleep(1 / fps)
