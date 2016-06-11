from __future__ import division
import time
import logging
from rdflib import Literal
from light9.namespaces import L9, RDF, DEV
from light9.collector.output import setListElem
from light9.collector.device import toOutputAttrs, resolve

log = logging.getLogger('collector')

def outputMap(graph, outputs):
    """From rdf config graph, compute a map of
       (device, outputattr) : (output, index)
    that explains which output index to set for any device update.
    """
    ret = {}

    outputByUri = {}  # universeUri : output
    for out in outputs:
        outputByUri[out.uri] = out

    for dc in graph.subjects(RDF.type, L9['DeviceClass']):
        for dev in graph.subjects(RDF.type, dc):
            output = outputByUri[graph.value(dev, L9['dmxUniverse'])]
            dmxBase = int(graph.value(dev, L9['dmxBase']).toPython())
            for row in graph.objects(dc, L9['attr']):
                outputAttr = graph.value(row, L9['outputAttr'])
                offset = int(graph.value(row, L9['dmxOffset']).toPython())
                index = dmxBase + offset - 1
                ret[(dev, outputAttr)] = (output, index)
                log.info('map %s,%s to %s,%s', dev, outputAttr, output, index)
    return ret
        
class Collector(object):
    def __init__(self, graph, outputs, clientTimeoutSec=10):
        self.graph = graph
        self.outputs = outputs
        self.clientTimeoutSec = clientTimeoutSec

        self.graph.addHandler(self.rebuildOutputMap)
        self.lastRequest = {} # client : (session, time, {(dev,attr): latestValue})

    def rebuildOutputMap(self):
        self.outputMap = outputMap(self.graph, self.outputs) # (device, attr) : (output, index)
        self.deviceType = {} # uri: type that's a subclass of Device
        self.remapOut = {} # (device, deviceAttr) : (start, end)
        for dc in self.graph.subjects(RDF.type, L9['DeviceClass']):
            for dev in self.graph.subjects(RDF.type, dc):
                self.deviceType[dev] = dc

                for remap in self.graph.objects(dev, L9['outputAttrRange']):
                    attr = self.graph.value(remap, L9['outputAttr'])
                    start = float(self.graph.value(remap, L9['start']))
                    end = float(self.graph.value(remap, L9['end']))
                    self.remapOut[(dev, attr)] = start, end

    def _forgetStaleClients(self, now):
        staleClients = []
        for c, (_, t, _) in self.lastRequest.iteritems():
            if t < now - self.clientTimeoutSec:
                staleClients.append(c)
        for c in staleClients:
            del self.lastRequest[c]

    def resolvedSettingsDict(self, settingsList):
        out = {}
        for d, a, v in settingsList:
            if (d, a) in out:
                out[(d, a)] = resolve(d, a, [out[(d, a)], v])
            else:
                out[(d, a)] = v
        return out

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

        if 0: # client updates their past requests?
            row = self.lastRequest.get(client)
            if row is not None:
                sess, _, prevClientSettings = row
                if sess != clientSession:
                    prevClientSettings = {}
            else:
                prevClientSettings = {}
        else: # client always provides all the nonzero settings it wants
            prevClientSettings = {}
            
        prevClientSettings.update(self.resolvedSettingsDict(settings))
        self.lastRequest[client] = (clientSession, now, prevClientSettings)

        # inputs that are omitted, implying a zero, should be added
        # back here if they would remap to something nonzero.
        
        deviceAttrs = {} # device: {deviceAttr: value}
        for _, _, lastSettings in self.lastRequest.itervalues():
            for (device, deviceAttr), value in lastSettings.iteritems():
                if (device, deviceAttr) in self.remapOut:
                    start, end = self.remapOut[(device, deviceAttr)]
                    value = Literal(start + float(value) * (end - start))

                attrs = deviceAttrs.setdefault(device, {})
                if deviceAttr in attrs:
                    value = resolve(device, deviceAttr, [attrs[deviceAttr], value])
                attrs[deviceAttr] = value

        outputAttrs = {} # device: {outputAttr: value}
        for d in deviceAttrs:
            try:
                devType = self.deviceType[d]
            except KeyError:
                log.warn("request for output to unconfigured device %s" % d)
                continue
            outputAttrs[d] = toOutputAttrs(devType, deviceAttrs[d])
        
        pendingOut = {} # output : values
        for out in self.outputs:
            pendingOut[out] = [0] * out.numChannels
        for device, attrs in outputAttrs.iteritems():
            for outputAttr, value in attrs.iteritems():
                self.setAttr(device, outputAttr, value, pendingOut)

        dt1 = 1000 * (time.time() - now)
        self.flush(pendingOut)
        dt2 = 1000 * (time.time() - now)
        if dt1 > 10:
            print "slow setAttrs: %.1fms -> flush -> %.1fms. lr %s da %s oa %s" % (
                dt1, dt2, len(self.lastRequest), len(deviceAttrs), len(outputAttrs)
            )

    def setAttr(self, device, outputAttr, value, pendingOut):
        output, index = self.outputMap[(device, outputAttr)]
        outList = pendingOut[output]
        setListElem(outList, index, value, combine=max)

    def flush(self, pendingOut):
        """write any changed outputs"""
        for out, vals in pendingOut.iteritems():
            out.update(vals)
            out.flush()
