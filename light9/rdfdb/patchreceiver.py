import logging, cyclone.httpclient, traceback, urllib
from twisted.internet import reactor
from light9 import networking
from light9.rdfdb.patch import Patch
log = logging.getLogger('syncedgraph')

class PatchReceiver(object):
    """
    runs a web server in this process and registers it with the rdfdb
    master. See onPatch for what happens when the rdfdb master sends
    us a patch
    """
    def __init__(self, rdfdbRoot, label, onPatch):
        """
        label is what we'll call ourselves to the rdfdb server

        onPatch is what we call back when the server sends a patch
        """
        self.rdfdbRoot = rdfdbRoot
        listen = reactor.listenTCP(0, cyclone.web.Application(handlers=[
            (r'/update', makePatchEndpoint(onPatch)),
        ]))
        port = listen._realPortNumber  # what's the right call for this?
        
        self.updateResource = 'http://%s:%s/update' % (
            networking.patchReceiverUpdateHost.value, port)
        log.info("listening on %s" % port)
        self._register(label)

    def _register(self, label):

        cyclone.httpclient.fetch(
            url=self.rdfdbRoot + 'graphClients',
            method='POST',
            headers={'Content-Type': ['application/x-www-form-urlencoded']},
            postdata=urllib.urlencode([('clientUpdate', self.updateResource),
                                       ('label', label)]),
            ).addCallbacks(self._done, log.error)
        log.info("registering with rdfdb")

    def _done(self, x):
        log.debug("registered with rdfdb")
    
        
def makePatchEndpointPutMethod(cb):
    def put(self):
        try:
            p = Patch(jsonRepr=self.request.body)
            log.debug("received patch -%d +%d" % (len(p.delGraph), len(p.addGraph)))
            cb(p)
        except:
            traceback.print_exc()
            raise
    return put

def makePatchEndpoint(cb):
    class Update(cyclone.web.RequestHandler):
        put = makePatchEndpointPutMethod(cb)
    return Update
