import json
from rdflib import URIRef, Literal
from greplin import scales
from txzmq import ZmqEndpoint, ZmqFactory, ZmqPullConnection
import logging

log = logging.getLogger('zmq')


def parseJsonMessage(msg):
    body = json.loads(msg)
    settings = []
    for device, attr, value in body['settings']:
        if isinstance(value, str) and value.startswith('http'):
            value = URIRef(value)
        else:
            value = Literal(value)
        settings.append((URIRef(device), URIRef(attr), value))
    return body['client'], body['clientSession'], settings, body['sendTime']


def startZmq(port, collector):
    stats = scales.collection(
        '/zmqServer',
        scales.PmfStat('setAttr', recalcPeriod=1),
        scales.RecentFpsStat('setAttrFps'),
    )

    zf = ZmqFactory()
    addr = 'tcp://*:%s' % port
    log.info('creating zmq endpoint at %r', addr)
    e = ZmqEndpoint('bind', addr)

    class Pull(ZmqPullConnection):
        #highWaterMark = 3
        def onPull(self, message):
            stats.setAttrFps.mark()
            with stats.setAttr.time():
                # todo: new compressed protocol where you send all URIs up
                # front and then use small ints to refer to devices and
                # attributes in subsequent requests.
                client, clientSession, settings, sendTime = parseJsonMessage(
                    message[0])
                collector.setAttrs(client, clientSession, settings, sendTime)

    Pull(zf, e)
