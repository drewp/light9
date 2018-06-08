from __future__ import division
import time
import logging
from rdflib import Literal
from light9.namespaces import L9, RDF
from light9.collector.output import setListElem
from light9.collector.device import toOutputAttrs, resolve

# types only
from rdflib import Graph, URIRef
from typing import List, Dict, Tuple, Any, TypeVar, Generic
from light9.collector.output import Output

ClientType = TypeVar('ClientType')
ClientSessionType = TypeVar('ClientSessionType')

log = logging.getLogger('collector')

def outputMap(graph, outputs):
    # type: (Graph, List[Output]) -> Dict[Tuple[URIRef, URIRef], Tuple[Output, int]]
    """From rdf config graph, compute a map of
       (device, outputattr) : (output, index)
    that explains which output index to set for any device update.
    """
    ret = {}

    outputByUri = {}  # universeUri : output
    for out in outputs:
        outputByUri[out.uri] = out

    for dc in graph.subjects(RDF.type, L9['DeviceClass']):
        log.info('mapping DeviceClass %s', dc)
        for dev in graph.subjects(RDF.type, dc):
            log.info('  mapping device %s', dev)
            universe = graph.value(dev, L9['dmxUniverse'])
            try:
                output = outputByUri[universe]
            except Exception:
                log.warn('dev %r :dmxUniverse %r', dev, universe)
                raise
            dmxBase = int(graph.value(dev, L9['dmxBase']).toPython())
            for row in graph.objects(dc, L9['attr']):
                outputAttr = graph.value(row, L9['outputAttr'])
                offset = int(graph.value(row, L9['dmxOffset']).toPython())
                index = dmxBase + offset - 1
                ret[(dev, outputAttr)] = (output, index)
                log.debug('    map %s to %s,%s', outputAttr, output, index)
    return ret
        
class Collector(Generic[ClientType, ClientSessionType]):
    def __init__(self, graph, outputs, listeners=None, clientTimeoutSec=10):
        # type: (Graph, List[Output], List[Listener], float) -> None
        self.graph = graph
        self.outputs = outputs
        self.listeners = listeners
        self.clientTimeoutSec = clientTimeoutSec
        self.initTime = time.time()
        self.allDevices = set()

        self.graph.addHandler(self.rebuildOutputMap)

        # client : (session, time, {(dev,devattr): latestValue})
        self.lastRequest = {} # type: Dict[Tuple[ClientType, ClientSessionType], Tuple[float, Dict[Tuple[URIRef, URIRef], float]]]

        # (dev, devAttr): value to use instead of 0
        self.stickyAttrs = {} # type: Dict[Tuple[URIRef, URIRef], float] 

    def rebuildOutputMap(self):
        self.outputMap = outputMap(self.graph, self.outputs) # (device, outputattr) : (output, index)
        self.deviceType = {} # uri: type that's a subclass of Device
        self.remapOut = {} # (device, deviceAttr) : (start, end)
        for dc in self.graph.subjects(RDF.type, L9['DeviceClass']):
            for dev in self.graph.subjects(RDF.type, dc):
                self.allDevices.add(dev)
                self.deviceType[dev] = dc

                for remap in self.graph.objects(dev, L9['outputAttrRange']):
                    attr = self.graph.value(remap, L9['outputAttr'])
                    start = float(self.graph.value(remap, L9['start']))
                    end = float(self.graph.value(remap, L9['end']))
                    self.remapOut[(dev, attr)] = start, end

    def _forgetStaleClients(self, now):
        # type: (float) -> None
        staleClientSessions = []
        for c, (t, _) in self.lastRequest.iteritems():
            if t < now - self.clientTimeoutSec:
                staleClientSessions.append(c)
        for c in staleClientSessions:
            log.info('forgetting stale client %r', c)
            del self.lastRequest[c]

    # todo: move to settings.py
    def resolvedSettingsDict(self, settingsList):
        # type: (List[Tuple[URIRef, URIRef, float]]) -> Dict[Tuple[URIRef, URIRef], float]
        out = {} # type: Dict[Tuple[URIRef, URIRef], float]
        for d, da, v in settingsList:
            if (d, da) in out:
                out[(d, da)] = resolve(d, da, [out[(d, da)], v])
            else:
                out[(d, da)] = v
        return out

    def _warnOnLateRequests(self, client, now, sendTime):
        requestLag = now - sendTime
        if requestLag > .1 and now > self.initTime + 10 and getattr(self, '_lastWarnTime', 0) < now - 3:
            self._lastWarnTime = now
            log.warn('collector.setAttrs from %s is running %.1fms after the request was made',
                     client, requestLag * 1000)

    def _merge(self, lastRequests):
        deviceAttrs = {} # device: {deviceAttr: value}       
        for _, lastSettings in lastRequests:
            for (device, deviceAttr), value in lastSettings.iteritems():
                if (device, deviceAttr) in self.remapOut:
                    start, end = self.remapOut[(device, deviceAttr)]
                    value = Literal(start + float(value) * (end - start))

                attrs = deviceAttrs.setdefault(device, {})
                if deviceAttr in attrs:
                    value = resolve(device, deviceAttr, [attrs[deviceAttr], value])
                attrs[deviceAttr] = value
                # list should come from the graph. these are attrs
                # that should default to holding the last position,
                # not going to 0.
                if deviceAttr in [L9['rx'], L9['ry'], L9['zoom'], L9['focus']]:
                    self.stickyAttrs[(device, deviceAttr)] = value

        # e.g. don't let an unspecified rotation go to 0
        for (d, da), v in self.stickyAttrs.iteritems():
            daDict = deviceAttrs.setdefault(d, {})
            if da not in daDict:
                daDict[da] = v
                    
        return deviceAttrs

    def setAttrs(self, client, clientSession, settings, sendTime):
        """
        settings is a list of (device, attr, value). These attrs are
        device attrs. We resolve conflicting values, process them into
        output attrs, and call Output.update/Output.flush to send the
        new outputs.

        client is a string naming the type of client. (client,
        clientSession) is a unique client instance.

        Each client session's last settings will be forgotten after
        clientTimeoutSec.
        """
        now = time.time()
        self._warnOnLateRequests(client, now, sendTime)

        self._forgetStaleClients(now)

        uniqueSettings = self.resolvedSettingsDict(settings)
        self.lastRequest[(client, clientSession)] = (now, uniqueSettings)

        deviceAttrs = self._merge(self.lastRequest.itervalues())
        
        outputAttrs = {} # device: {outputAttr: value}
        for d in self.allDevices:
            try:
                devType = self.deviceType[d]
            except KeyError:
                log.warn("request for output to unconfigured device %s" % d)
                continue
            try:
                outputAttrs[d] = toOutputAttrs(devType, deviceAttrs.get(d, {}))
                if self.listeners:
                    self.listeners.outputAttrsSet(d, outputAttrs[d], self.outputMap)
            except Exception as e:
                log.error('failing toOutputAttrs on %s: %r', d, e)
        
        pendingOut = {} # output : values
        for out in self.outputs:
            pendingOut[out] = [0] * out.numChannels

        for device, attrs in outputAttrs.iteritems():
            for outputAttr, value in attrs.iteritems():
                self.setAttr(device, outputAttr, value, pendingOut)

        dt1 = 1000 * (time.time() - now)
        self.flush(pendingOut)
        dt2 = 1000 * (time.time() - now)
        if dt1 > 30:
            log.warn("slow setAttrs: %.1fms -> flush -> %.1fms. lr %s da %s oa %s" % (
                dt1, dt2, len(self.lastRequest), len(deviceAttrs), len(outputAttrs)
            ))

    def setAttr(self, device, outputAttr, value, pendingOut):
        output, index = self.outputMap[(device, outputAttr)]
        outList = pendingOut[output]
        setListElem(outList, index, value, combine=max)

    def flush(self, pendingOut):
        """write any changed outputs"""
        for out, vals in pendingOut.iteritems():
            out.update(vals)
            out.flush()
