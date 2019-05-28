import logging, traceback, time, json
from typing import List, Tuple, Any, Dict

import cyclone.websocket
from rdflib import URIRef

from light9.newtypes import DeviceUri, DmxIndex, DmxMessageIndex, OutputAttr, OutputValue
from light9.collector.output import Output as OutputInstance

log = logging.getLogger('weblisteners')


class WebListeners(object):

    def __init__(self) -> None:
        self.clients: List[Tuple[Any, Dict[URIRef, Dict[URIRef, Any]]]] = []
        self.pendingMessageForDev: Dict[DeviceUri, Tuple[
            Dict[OutputAttr, OutputValue],
            Dict[Tuple[DeviceUri, OutputAttr],
                 Tuple[OutputInstance, DmxMessageIndex]]]] = {}
        self.lastFlush = 0

    def addClient(self, client: cyclone.websocket.WebSocketHandler):
        self.clients.append((client, {}))  # seen = {dev: attrs}
        log.info('added client %s %s', len(self.clients), client)

    def delClient(self, client: cyclone.websocket.WebSocketHandler):
        self.clients = [(c, t) for c, t in self.clients if c != client]
        log.info('delClient %s, %s left', client, len(self.clients))

    def outputAttrsSet(self, dev: DeviceUri, attrs: Dict[OutputAttr, Any],
                       outputMap: Dict[Tuple[DeviceUri, OutputAttr],
                                       Tuple[OutputInstance, DmxMessageIndex]]):
        """called often- don't be slow"""

        self.pendingMessageForDev[dev] = (attrs, outputMap)
        try:
            self._flush()
        except Exception:
            traceback.print_exc()
            raise

    def _flush(self):
        now = time.time()
        if now < self.lastFlush + .05 or not self.clients:
            return
        self.lastFlush = now

        while self.pendingMessageForDev:
            dev, (attrs, outputMap) = self.pendingMessageForDev.popitem()

            msg = None  # lazy, since makeMsg is slow

            # this omits repeats, but can still send many
            # messages/sec. Not sure if piling up messages for the browser
            # could lead to slowdowns in the real dmx output.
            for client, seen in self.clients:
                if seen.get(dev) == attrs:
                    continue
                if msg is None:
                    msg = self.makeMsg(dev, attrs, outputMap)

                seen[dev] = attrs
                client.sendMessage(msg)

    def makeMsg(self, dev: DeviceUri, attrs: Dict[OutputAttr, Any],
                outputMap: Dict[Tuple[DeviceUri, OutputAttr],
                                Tuple[OutputInstance, DmxMessageIndex]]):
        attrRows = []
        for attr, val in attrs.items():
            output, bufIndex = outputMap[(dev, attr)]
            dmxIndex = DmxIndex(bufIndex + 1)
            attrRows.append({
                'attr': attr.rsplit('/')[-1],
                'val': val,
                'chan': (output.shortId(), dmxIndex)
            })
        attrRows.sort(key=lambda r: r['chan'])
        for row in attrRows:
            row['chan'] = '%s %s' % (row['chan'][0], row['chan'][1])

        msg = json.dumps({'outputAttrsSet': {
            'dev': dev,
            'attrs': attrRows
        }},
                         sort_keys=True)
        return msg
