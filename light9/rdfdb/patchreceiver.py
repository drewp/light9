import logging, cyclone.httpclient, traceback, urllib
from twisted.internet import reactor
from light9.rdfdb.rdflibpatch import patchQuads
from light9.rdfdb.patch import Patch
log = logging.getLogger('syncedgraph')

class PatchReceiver(object):
    """
    runs a web server in this process and registers it with the rdfdb
    master. See onPatch for what happens when the rdfdb master sends
    us a patch
    """
    def __init__(self, graph, label, initiallySynced):
        """
        label is what we'll call ourselves to the rdfdb server

        initiallySynced is a deferred that we'll call back when we get
        the first patch from the server
        """
        self.graph = graph
        self.initiallySynced = initiallySynced
        
        listen = reactor.listenTCP(0, cyclone.web.Application(handlers=[
            (r'/update', makePatchEndpoint(self._onPatch)),
        ]))
        port = listen._realPortNumber  # what's the right call for this?
        self.updateResource = 'http://localhost:%s/update' % port
        log.info("listening on %s" % port)
        self._register(label)

    def _onPatch(self, p):
        """
        central server has sent us a patch
        """
        patchQuads(self.graph, p.delQuads, p.addQuads, perfect=True)
        log.info("graph now has %s statements" % len(self.graph))
        try:
            self.updateOnPatch(p)
        except Exception:
            # don't reflect this back to the server; we did
            # receive its patch correctly.
            traceback.print_exc()

        if self.initiallySynced:
            self.initiallySynced.callback(None)
            self.initiallySynced = None

    def _register(self, label):

        def done(x):
            log.debug("registered with rdfdb")

        cyclone.httpclient.fetch(
            url='http://localhost:8051/graphClients',
            method='POST',
            headers={'Content-Type': ['application/x-www-form-urlencoded']},
            postdata=urllib.urlencode([('clientUpdate', self.updateResource),
                                       ('label', label)]),
            ).addCallbacks(done, log.error)
        log.info("registering with rdfdb")

        
def makePatchEndpointPutMethod(cb):
    def put(self):
        try:
            p = Patch(jsonRepr=self.request.body)
            log.info("received patch -%d +%d" % (len(p.delGraph), len(p.addGraph)))
            cb(p)
        except:
            traceback.print_exc()
            raise
    return put

def makePatchEndpoint(cb):
    class Update(cyclone.web.RequestHandler):
        put = makePatchEndpointPutMethod(cb)
    return Update
