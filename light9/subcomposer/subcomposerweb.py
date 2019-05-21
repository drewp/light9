import logging
import cyclone.web, cyclone.websocket, cyclone.httpclient
from lib.cycloneerr import PrettyErrorHandler
from light9 import networking
from rdflib import URIRef, Literal
from twisted.internet import reactor
log = logging.getLogger('web')


def init(graph, session, currentSub):
    SFH = cyclone.web.StaticFileHandler
    app = cyclone.web.Application(handlers=[
        (r'/()', SFH, {
            'path': 'light9/subcomposer',
            'default_filename': 'index.html'
        }),
        (r'/toggle', Toggle),
    ],
                                  debug=True,
                                  graph=graph,
                                  currentSub=currentSub)
    reactor.listenTCP(networking.subComposer.port, app)
    log.info("listening on %s" % networking.subComposer.port)


class Toggle(PrettyErrorHandler, cyclone.web.RequestHandler):

    def post(self):
        chan = URIRef(self.get_argument('chan'))
        sub = self.settings.currentSub()

        chanKey = Literal(chan.rsplit('/', 1)[1])
        old = sub.get_levels().get(chanKey, 0)

        sub.editLevel(chan, 0 if old else 1)
