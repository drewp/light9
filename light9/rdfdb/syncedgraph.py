from rdflib import ConjunctiveGraph, RDFS
import logging, cyclone.httpclient, traceback, urllib
from twisted.internet import reactor
log = logging.getLogger()
from light9.rdfdb.patch import Patch, ALLSTMTS
from light9.rdfdb.rdflibpatch import patchQuads

def sendPatch(putUri, patch):
    # this will take args for sender, etc
    body = patch.jsonRepr
    log.debug("send body: %r" % body)
    def ok(done):
        if not str(done.code).startswith('2'):
            raise ValueError("sendPatch request failed %s: %s" % (done.code, done.body))
        log.debug("sendPatch finished, response: %s" % done.body)
        return done

    return cyclone.httpclient.fetch(
        url=putUri,
        method='PUT',
        headers={'Content-Type': ['application/json']},
        postdata=body,
        ).addCallback(ok)

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

class GraphWatchers(object):
    """
    store the current handlers that care about graph changes
    """
    def __init__(self):
        self._handlersSp = {} # (s,p): set(handlers)

    def addSubjPredWatcher(self, func, s, p):
        if func is None:
            return
        key = s, p
        try:
            self._handlersSp.setdefault(key, set()).add(func)
        except Exception:
            print "with key %r and func %r" % (key, func)
            raise

    def whoCares(self, patch):
        """what handler functions would care about the changes in this patch"""
        self.dependencies()
        affectedSubjPreds = set([(s, p) for s, p, o, c in patch.addQuads]+
                                [(s, p) for s, p, o, c in patch.delQuads])
        
        ret = set()
        for (s,p), func in self._handlersSp.iteritems():
            if (s,p) in affectedSubjPreds:
                ret.update(func)
        return ret

    def dependencies(self):
        """
        for debugging, make a list of all the active handlers and what
        data they depend on. This is meant for showing on the web ui
        for browsing.
        """
        print "whocares"
        from pprint import pprint
        pprint(self._handlersSp)
        

class SyncedGraph(object):
    """
    graph for clients to use. Changes are synced with the master graph
    in the rdfdb process. 
    
    This api is like rdflib.Graph but it can also call you back when
    there are graph changes to the parts you previously read.
    """
    def __init__(self, label):
        """
        label is a string that the server will display in association
        with your connection
        """
        _graph = self._graph = ConjunctiveGraph()
        self._watchers = GraphWatchers()
        
        def onPatch(p):
            patchQuads(_graph, p.delQuads, p.addQuads)
            log.info("graph now has %s statements" % len(_graph))
            try:
                self.updateOnPatch(p)
            except Exception:
                # don't reflect this back to the server; we did
                # receive its patch correctly.
                traceback.print_exc()

        listen = reactor.listenTCP(0, cyclone.web.Application(handlers=[
            (r'/update', makePatchEndpoint(onPatch)),
        ]))
        port = listen._realPortNumber  # what's the right call for this?
        self.updateResource = 'http://localhost:%s/update' % port
        log.info("listening on %s" % port)
        self.register(label)
        self.currentFunc = None

    def register(self, label):

        def done(x):
            print "registered", x.body

        cyclone.httpclient.fetch(
            url='http://localhost:8051/graphClients',
            method='POST',
            headers={'Content-Type': ['application/x-www-form-urlencoded']},
            postdata=urllib.urlencode([('clientUpdate', self.updateResource),
                                       ('label', label)]),
            ).addCallbacks(done, log.error)
        log.info("registering with rdfdb")

    def patch(self, p):
        """send this patch to the server and apply it to our local graph and run handlers"""
        # currently this has to round-trip. But I could apply the
        # patch here and have the server not bounce it back to me
        return sendPatch('http://localhost:8051/patches', p)

    def addHandler(self, func):
        """
        run this (idempotent) func, noting what graph values it
        uses. Run it again in the future if there are changes to those
        graph values. The func might use different values during that
        future call, and those will be what we watch for next.
        """

        # if we saw this func before, we need to forget the old
        # callbacks it wanted and replace with the new ones we see
        # now.

        # if one handler func calls another, does that break anything?
        # maybe not?

        # no plan for sparql queries yet. Hook into a lower layer that
        # reveals all their statement fetches? Just make them always
        # new? Cache their results, so if i make the query again and
        # it gives the same result, I don't call the handler?
        
        self.currentFunc = func
        try:
            func()
        finally:
            self.currentFunc = None

    def updateOnPatch(self, p):
        """
        patch p just happened to the graph; call everyone back who
        might care, and then notice what data they depend on now
        """
        for func in self._watchers.whoCares(p):
            # and forget the old one!
            self.addHandler(func)

    def _assertCurrent(self):
        if self.currentFunc is None:
            # this may become a warning later
            raise ValueError("asked for graph data outside of a handler")

    # these just call through to triples() so it might be possible to
    # watch just that one
    def value(self, subj, pred):
        self._assertCurrent()
        self._watchers.addSubjPredWatcher(self.currentFunc, subj, pred)
        return self._graph.value(subj, pred)

    def objects(self, subject=None, predicate=None):
        self._assertCurrent()
        self._watchers.addSubjPredWatcher(self.currentFunc, subject, predicate)
        return self._graph.objects(subject, predicate)
    
    def label(self, uri):
        self._assertCurrent()
        return self.value(uri, RDFS.label)
