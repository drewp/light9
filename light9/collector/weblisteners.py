import logging, traceback, time, json
log = logging.getLogger('weblisteners')


class WebListeners(object):

    def __init__(self):
        self.clients = []
        self.pendingMessageForDev = {}  # dev: (attrs, outputmap)
        self.lastFlush = 0

    def addClient(self, client):
        self.clients.append([client, {}])  # seen = {dev: attrs}
        log.info('added client %s %s', len(self.clients), client)

    def delClient(self, client):
        self.clients = [[c, t] for c, t in self.clients if c != client]
        log.info('delClient %s, %s left', client, len(self.clients))

    def outputAttrsSet(self, dev, attrs, outputMap):
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

    def makeMsg(self, dev, attrs, outputMap):
        attrRows = []
        for attr, val in attrs.items():
            output, index = outputMap[(dev, attr)]
            attrRows.append({
                'attr': attr.rsplit('/')[-1],
                'val': val,
                'chan': (output.shortId(), index + 1)
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
