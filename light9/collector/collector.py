from __future__ import division
import time
from webcolors import hex_to_rgb
from light9.namespaces import L9, RDF
from light9.collector.output import setListElem


#class Device(object):
#    def setAttrs():
#        pass

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
    
    return ret
        
class Collector(object):
    def __init__(self, config, outputs, clientTimeoutSec=10):
        self.config = config
        self.outputs = outputs
        self.clientTimeoutSec = clientTimeoutSec
        self.outputMap = outputMap(config, outputs) # (device, attr) : (output, index)
        self.lastRequest = {} # client : (session, time, settings)

    def _forgetStaleClients(self, now):
        staleClients = []
        for c, (_, t, _) in self.lastRequest.iteritems():
            if t < now - self.clientTimeoutSec:
                staleClients.append(c)
        for c in staleClients:
            del self.lastRequest[c]
        
    def setAttrs(self, client, clientSession, settings):
        """
        settings is a list of (device, attr, value). Interpret rgb colors,
        resolve conflicting values, and call
        Output.update/Output.flush to send the new outputs
        """
        now = time.time()
        self.lastRequest[client] = (clientSession, now, settings)

        self._forgetStaleClients(now)
        
        pendingOut = {} # output : values
        for _, _, settings in self.lastRequest.itervalues():
            for device, attr, value in settings:
                self.setAttr(device, attr, value, pendingOut)

        self.flush(pendingOut)

    def setAttr(self, device, attr, value, pendingOut):
        if attr == L9['color']:
            [self.setAttr(device, a, x / 255, pendingOut) for a, x in zip(
                [L9['red'], L9['green'], L9['blue']],
                hex_to_rgb(value))]
            return
            
        output, index = self.outputMap[(device, attr)]
        outList = pendingOut.setdefault(output, [])
        setListElem(outList, index, int(float(value) * 255), combine=max)

    def flush(self, pendingOut):
        """write any changed outputs"""
        for out, vals in pendingOut.iteritems():
            out.update(vals)
            out.flush()
