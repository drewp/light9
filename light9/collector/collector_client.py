from light9 import networking
from light9.effect.settings import DeviceSettings
from twisted.internet import defer
from txzmq import ZmqEndpoint, ZmqFactory, ZmqPushConnection
import json, time, logging
import treq

log = logging.getLogger('coll_client')

_zmqClient = None


class TwistedZmqClient(object):
    def __init__(self, service):
        zf = ZmqFactory()
        e = ZmqEndpoint('connect', 'tcp://%s:%s' % (service.host, service.port))
        self.conn = ZmqPushConnection(zf, e)

    def send(self, msg):
        self.conn.push(msg)


def toCollectorJson(client, session, settings):
    assert isinstance(settings, DeviceSettings)
    return json.dumps({
        'settings': settings.asList(),
        'client': client,
        'clientSession': session,
        'sendTime': time.time(),
    })


def sendToCollectorZmq(msg):
    global _zmqClient
    if _zmqClient is None:
        _zmqClient = TwistedZmqClient(networking.collectorZmq)
    _zmqClient.send(msg)
    return defer.succeed(0)


def sendToCollector(client, session, settings, useZmq=False):
    """deferred to the time in seconds it took to get a response from collector"""
    sendTime = time.time()
    msg = toCollectorJson(client, session, settings)

    if useZmq:
        d = sendToCollectorZmq(msg)
    else:
        d = treq.put(networking.collector.path('attrs'), data=msg, timeout=1)

    def onDone(result):
        dt = time.time() - sendTime
        if dt > .1:
            log.warn('sendToCollector request took %.1fms', dt * 1000)
        return dt

    d.addCallback(onDone)

    def onErr(err):
        log.warn('sendToCollector failed: %r', err)

    d.addErrback(onErr)
    return d
