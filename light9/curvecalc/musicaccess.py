import json
from louie import dispatcher
from rdflib import URIRef
from light9 import networking
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred
from zope.interface import implements
from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer


class GatherJson(Protocol):
    """calls back the 'finished' deferred with the parsed json data we
    received"""

    def __init__(self, finished):
        self.finished = finished
        self.buf = ""

    def dataReceived(self, bytes):
        self.buf += bytes

    def connectionLost(self, reason):
        self.finished.callback(json.loads(self.buf))


class StringProducer(object):
    # http://twistedmatrix.com/documents/current/web/howto/client.html
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class Music:

    def __init__(self):
        self.recenttime = 0
        self.player = Agent(reactor)
        self.timePath = networking.musicPlayer.path("time")

    def current_time(self):
        """return deferred which gets called with the current
        time. This gets called really often"""
        d = self.player.request("GET", self.timePath)
        d.addCallback(self._timeReturned)
        return d

    def _timeReturned(self, response):
        done = Deferred()
        done.addCallback(self._bodyReceived)
        response.deliverBody(GatherJson(done))
        return done

    def _bodyReceived(self, data):
        if 't' in data:
            dispatcher.send("input time", val=data['t'])
        if 'song' in data and data['song']:
            dispatcher.send("current_player_song", song=URIRef(data['song']))
        return data['t']  # pass along to the real receiver

    def playOrPause(self, t=None):
        if t is None:
            # could be better
            self.current_time().addCallback(lambda t: self.playOrPause(t))
        else:
            self.player.request("POST",
                                networking.musicPlayer.path("seekPlayOrPause"),
                                bodyProducer=StringProducer(json.dumps({"t":
                                                                        t})))
