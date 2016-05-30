from __future__ import division
import time
import logging
from light9.namespaces import L9, RDF, DEV
from light9.collector.output import setListElem
from light9.collector.device import toOutputAttrs

log = logging.getLogger('collector')

def outputMap(graph, outputs):
    """From rdf config graph, compute a map of
       (device, attr) : (output, index)
    that explains which output index to set for any device update.
    """
    ret = {}

    outIndex = {} # port : (output, index)
    for out in outputs:
        for index, uri in out.allConnections():
            outIndex[uri] = (out, index)

    for dev in graph.subjects(RDF.type, L9['Device']):
        for attr, connectedTo in graph.predicate_objects(dev):
            if attr == RDF.type:
                continue
            outputPorts = list(graph.subjects(L9['connectedTo'], connectedTo))
            if len(outputPorts) == 0:
                raise ValueError('no output port :connectedTo %r' % connectedTo)
            elif len(outputPorts) > 1:
                raise ValueError('multiple output ports (%r) :connectedTo %r' %
                                 (outputPorts, connectedTo))
            else:
                output, index = outIndex[outputPorts[0]]
            ret[(dev, attr)] = output, index
            log.debug('outputMap (%r, %r) -> %r, %r', dev, attr, output, index)
    
    return ret
        
class Collector(object):
    def __init__(self, config, outputs, clientTimeoutSec=10):
        self.config = config
        self.outputs = outputs
        self.clientTimeoutSec = clientTimeoutSec
        self.outputMap = outputMap(config, outputs) # (device, attr) : (output, index)
        self.lastRequest = {} # client : (session, time, {(dev,attr): latestValue})

    def _forgetStaleClients(self, now):
        staleClients = []
        for c, (_, t, _) in self.lastRequest.iteritems():
            if t < now - self.clientTimeoutSec:
                staleClients.append(c)
        for c in staleClients:
            del self.lastRequest[c]

    def _deviceType(self, d):
        for t in self.config.objects(d, RDF.type):
            if t == L9['Device']:
                continue
            return t
        
    def setAttrs(self, client, clientSession, settings):
        """
        settings is a list of (device, attr, value). These attrs are
        device attrs. We resolve conflicting values, process them into
        output attrs, and call Output.update/Output.flush to send the
        new outputs.

        Call with settings=[] to ping us that your session isn't dead.
        """
        now = time.time()

        self._forgetStaleClients(now)
        row = self.lastRequest.get(client)
        if row is not None:
            sess, _, prevClientSettings = row
            if sess != clientSession:
                prevClientSettings = {}
        else:
            prevClientSettings = {}
        for d, a, v in settings:
            prevClientSettings[(d, a)] = v
        self.lastRequest[client] = (clientSession, now, prevClientSettings)


        deviceAttrs = {} # device: {attr: value}
        for _, _, settings in self.lastRequest.itervalues():
            for (device, attr), value in settings.iteritems():
                # resolving conflicts goes around here
                deviceAttrs.setdefault(device, {})[attr] = value

        outputAttrs = {} # device: {attr: value}
        for d in deviceAttrs:
            outputAttrs[d] = toOutputAttrs(self._deviceType(d), deviceAttrs[d])
        
        pendingOut = {} # output : values
        for device, attrs in outputAttrs.iteritems():
            for attr, value in attrs.iteritems():
                self.setAttr(device, attr, value, pendingOut)

        self.flush(pendingOut)

    def setAttr(self, device, attr, value, pendingOut):
        output, index = self.outputMap[(device, attr)]
        outList = pendingOut.setdefault(output, [])
        setListElem(outList, index, value, combine=max)

    def flush(self, pendingOut):
        """write any changed outputs"""
        for out, vals in pendingOut.iteritems():
            out.update(vals)
            out.flush()
