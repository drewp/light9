import time
import logging
from typing import cast, List, Dict, Tuple, Optional, Set

from rdflib import Graph, Literal

from light9.collector.device import toOutputAttrs, resolve
from light9.collector.output import Output as OutputInstance
from light9.collector.weblisteners import WebListeners
from light9.namespaces import L9, RDF
from rdfdb.syncedgraph import SyncedGraph
from light9.newtypes import ClientType, ClientSessionType, OutputUri, DeviceUri, DeviceClass, DmxIndex, DmxMessageIndex, DeviceAttr, OutputAttr, OutputValue, UnixTime, OutputRange
log = logging.getLogger('collector')


def outputMap(
        graph: Graph, outputs: List[OutputInstance]
) -> Dict[Tuple[DeviceUri, OutputAttr], Tuple[OutputInstance, DmxMessageIndex]]:
    """From rdf config graph, compute a map of
       (device, outputattr) : (output, index)
    that explains which output index to set for any device update.
    """
    ret = {}

    outputByUri: Dict[OutputUri, OutputInstance] = {}
    for out in outputs:
        outputByUri[OutputUri(out.uri)] = out

    for dc in graph.subjects(RDF.type, L9['DeviceClass']):
        log.info('mapping DeviceClass %s', dc)
        for dev in graph.subjects(RDF.type, dc):
            dev = cast(DeviceUri, dev)
            log.info('  mapping device %s', dev)
            universe = cast(OutputUri, graph.value(dev, L9['dmxUniverse']))
            try:
                output = outputByUri[universe]
            except Exception:
                log.warn('dev %r :dmxUniverse %r', dev, universe)
                raise
            base = graph.value(dev, L9['dmxBase'])
            if base is None:
                raise ValueError('no :dmxBase for %s' % dev)
            dmxBase = DmxIndex(cast(Literal, base).toPython())
            for row in graph.objects(dc, L9['attr']):
                outputAttr = cast(OutputAttr,
                                  graph.value(row, L9['outputAttr']))
                offset = DmxIndex(
                    cast(Literal, graph.value(row, L9['dmxOffset'])).toPython())
                index = DmxMessageIndex(dmxBase + offset - 1)
                ret[(dev, outputAttr)] = (output, index)
                log.debug('    map %s to %s,%s', outputAttr, output, index)
    return ret


class Collector:

    def __init__(self,
                 graph: SyncedGraph,
                 outputs: List[OutputInstance],
                 listeners: Optional[WebListeners] = None,
                 clientTimeoutSec: float = 10):
        self.graph = graph
        self.outputs = outputs
        self.listeners = listeners
        self.clientTimeoutSec = clientTimeoutSec
        self.initTime = time.time()
        self.allDevices: Set[DeviceUri] = set()

        self.graph.addHandler(self.rebuildOutputMap)

        # client : (session, time, {(dev,devattr): latestValue})
        self.lastRequest: Dict[Tuple[ClientType, ClientSessionType], Tuple[
            UnixTime, Dict[Tuple[DeviceUri, DeviceAttr], float]]] = {}

        # (dev, devAttr): value to use instead of 0
        self.stickyAttrs: Dict[Tuple[DeviceUri, DeviceAttr], float] = {}

    def rebuildOutputMap(self):
        self.outputMap = outputMap(self.graph, self.outputs)
        self.deviceType: Dict[DeviceUri, DeviceClass] = {}
        self.remapOut: Dict[Tuple[DeviceUri, DeviceAttr], OutputRange] = {}
        for dc in self.graph.subjects(RDF.type, L9['DeviceClass']):
            for dev in map(DeviceUri, self.graph.subjects(RDF.type, dc)):
                self.allDevices.add(dev)
                self.deviceType[dev] = dc

                for remap in self.graph.objects(dev, L9['outputAttrRange']):
                    attr = OutputAttr(self.graph.value(remap, L9['outputAttr']))
                    start = cast(Literal,
                                 self.graph.value(remap,
                                                  L9['start'])).toPython()
                    end = cast(Literal, self.graph.value(remap,
                                                         L9['end'])).toPython()
                    self.remapOut[(dev, attr)] = OutputRange((start, end))

    def _forgetStaleClients(self, now):
        # type: (float) -> None
        staleClientSessions = []
        for c, (t, _) in self.lastRequest.items():
            if t < now - self.clientTimeoutSec:
                staleClientSessions.append(c)
        for c in staleClientSessions:
            log.info('forgetting stale client %r', c)
            del self.lastRequest[c]

    # todo: move to settings.py
    def resolvedSettingsDict(
            self, settingsList: List[Tuple[DeviceUri, DeviceAttr, float]]
    ) -> Dict[Tuple[DeviceUri, DeviceAttr], float]:
        out: Dict[Tuple[DeviceUri, DeviceAttr], float] = {}
        for d, da, v in settingsList:
            if (d, da) in out:
                out[(d, da)] = resolve(d, da, [out[(d, da)], v])
            else:
                out[(d, da)] = v
        return out

    def _warnOnLateRequests(self, client, now, sendTime):
        requestLag = now - sendTime
        if requestLag > .1 and now > self.initTime + 10 and getattr(
                self, '_lastWarnTime', 0) < now - 3:
            self._lastWarnTime = now
            log.warn(
                'collector.setAttrs from %s is running %.1fms after the request was made',
                client, requestLag * 1000)

    def _merge(self, lastRequests):
        deviceAttrs: Dict[DeviceUri, Dict[DeviceAttr, float]] = {
        }  # device: {deviceAttr: value}
        for _, lastSettings in lastRequests:
            for (device, deviceAttr), value in lastSettings.items():
                if (device, deviceAttr) in self.remapOut:
                    start, end = self.remapOut[(device, deviceAttr)]
                    value = Literal(start + float(value) * (end - start))

                attrs = deviceAttrs.setdefault(device, {})
                if deviceAttr in attrs:
                    value = resolve(device, deviceAttr,
                                    [attrs[deviceAttr], value])
                attrs[deviceAttr] = value
                # list should come from the graph. these are attrs
                # that should default to holding the last position,
                # not going to 0.
                if deviceAttr in [L9['rx'], L9['ry'], L9['zoom'], L9['focus']]:
                    self.stickyAttrs[(device, deviceAttr)] = value

        # e.g. don't let an unspecified rotation go to 0
        for (d, da), v in self.stickyAttrs.items():
            daDict = deviceAttrs.setdefault(d, {})
            if da not in daDict:
                daDict[da] = v

        return deviceAttrs

    def setAttrs(self, client: ClientType, clientSession: ClientSessionType,
                 settings: List[Tuple[DeviceUri, DeviceAttr, float]],
                 sendTime: UnixTime):
        """
        settings is a list of (device, attr, value). These attrs are
        device attrs. We resolve conflicting values, process them into
        output attrs, and call Output.update to send the new outputs.

        client is a string naming the type of client. (client,
        clientSession) is a unique client instance.

        Each client session's last settings will be forgotten after
        clientTimeoutSec.
        """
        now = UnixTime(time.time())
        self._warnOnLateRequests(client, now, sendTime)

        self._forgetStaleClients(now)

        uniqueSettings = self.resolvedSettingsDict(settings)
        self.lastRequest[(client, clientSession)] = (now, uniqueSettings)

        deviceAttrs = self._merge(iter(self.lastRequest.values()))

        outputAttrs: Dict[DeviceUri, Dict[OutputAttr, OutputValue]] = {}
        for d in self.allDevices:
            try:
                devType = self.deviceType[d]
            except KeyError:
                log.warn("request for output to unconfigured device %s" % d)
                continue
            try:
                outputAttrs[d] = toOutputAttrs(devType, deviceAttrs.get(d, {}))
                if self.listeners:
                    self.listeners.outputAttrsSet(d, outputAttrs[d],
                                                  self.outputMap)
            except Exception as e:
                log.error('failing toOutputAttrs on %s: %r', d, e)

        pendingOut: Dict[OutputUri, Tuple[OutputInstance, bytearray]] = {}
        for out in self.outputs:
            pendingOut[OutputUri(out.uri)] = (out, bytearray(512))

        for device, attrs in outputAttrs.items():
            for outputAttr, value in attrs.items():
                output, _index = self.outputMap[(device, outputAttr)]
                outputUri = OutputUri(output.uri)
                index = DmxMessageIndex(_index)
                _, outArray = pendingOut[outputUri]
                if outArray[index] != 0:
                    raise ValueError(f"someone already wrote to index {index}")
                outArray[index] = value

        dt1 = 1000 * (time.time() - now)
        for uri, (out, buf) in pendingOut.items():
            out.update(bytes(buf))
        dt2 = 1000 * (time.time() - now)
        if dt1 > 30:
            log.warn(
                "slow setAttrs: %.1fms -> flush -> %.1fms. lr %s da %s oa %s" %
                (dt1, dt2, len(
                    self.lastRequest), len(deviceAttrs), len(outputAttrs)))
