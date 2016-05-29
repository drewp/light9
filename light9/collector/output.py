from rdflib import URIRef
import sys

def setListElem(outList, index, value, fill=0, combine=lambda old, new: new):
    if len(outList) < index:
        outList.extend([fill] * (index - len(outList)))
    if len(outList) <= index:
        outList.append(value)
    else:
        outList[index] = combine(outList[index], value)

class Output(object):
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
    def __init__(self, baseUri, channels):
        self.baseUri = baseUri
        self.channels = channels

    def allConnections(self):
        return ((i, URIRef('%sc%s' % (self.baseUri, i + 1)))
                for i in range(self.channels))

    def flush(self):
        pass


class EnttecDmx(DmxOutput):
    def __init__(self, baseUri, channels, devicePath='/dev/dmx0'):
        DmxOutput.__init__(self, baseUri, channels)

        sys.path.append("dmx_usb_module")
        from dmx import Dmx
        self.dev = Dmx(devicePath)

    def update(self, values):
         # I was outputting on 76 and it was turning on the light at
        # dmx75. So I added the 0 byte.
        packet = '\x00' + ''.join(map(chr, values)) + "\x55"
        self.dev.write(packet)

class Udmx(DmxOutput):
    def __init__(self, baseUri, channels):
        DmxOutput.__init__(self, baseUri, channels)
        
        from light9.io.udmx import Udmx
        self.dev = Udmx()

    def update(self, values):
        self.dev.SendDMX(''.join(map(chr, values)))
