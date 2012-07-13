from rdflib import ConjunctiveGraph, Graph
import json, logging, cyclone.httpclient, traceback, urllib
from twisted.internet import reactor
log = logging.getLogger()

ALLSTMTS = (None, None, None)

class Patch(object):
    """
    the json representation includes the {"patch":...} wrapper
    """
    def __init__(self, jsonRepr=None, addQuads=None, delTriples=None,
                 addGraph=None, delGraph=None):
        self._jsonRepr = jsonRepr
        self._addQuads, self._delTriples = addQuads, delTriples
        self._addGraph, self._delGraph = addGraph, delGraph

        if self._jsonRepr is not None:
            body = json.loads(self._jsonRepr)
            self._delGraph = Graph()
            self._delGraph.parse(data=body['patch']['deletes'], format='nt')
            self._addGraph = ConjunctiveGraph()
            self._addGraph.parse(data=body['patch']['adds'], format='nquads')

    @property
    def addQuads(self):
        if self._addQuads is None:
            if self._addGraph is not None:
                self._addQuads = list(self._addGraph.quads(ALLSTMTS))
            else:
                raise
        return self._addQuads

    @property
    def delTriples(self):
        if self._delTriples is None:
            if self._delGraph is not None:
                self._delTriples = list(self._delGraph.triples(ALLSTMTS))
            else:
                raise
        return self._delTriples

    @property
    def addGraph(self):
        if self._addGraph is None:
            raise
        return self._addGraph

    @property
    def delGraph(self):
        if self._delGraph is None:
            raise
        return self._delGraph

    @property
    def jsonRepr(self):
        if self._jsonRepr is None:
            addGraph = ConjunctiveGraph()
            #addGraph.addN(addQuads) # no effect on nquad output
            for s,p,o,c in self.addQuads:
                addGraph.get_context(c).add((s,p,o))
                #addGraph.store.add((s,p,o), c) # no effect on nquad output
            delGraph = Graph()
            for s in self.delTriples:
                delGraph.add(s)
            self._jsonRepr = json.dumps({"patch": {
                'adds':addGraph.serialize(format='nquads'),
                'deletes':delGraph.serialize(format='nt'),
                }})
        return self._jsonRepr

def sendPatch(putUri, patch):

    # this will take args for sender, etc
    body = patch.jsonRepr
    log.debug("send body: %r" % body)
    def ok(done):
        if not str(done.code).startswith('2'):
            raise ValueError("sendPatch request failed %s: %s" % (done.code, done.body))
        log.debug("sendPatch finished, response: %s" % done.body)
        return done

    def err(e):
        log.warn("sendPatch failed %r" % e)
        raise e

    return cyclone.httpclient.fetch(
        url=putUri,
        method='PUT',
        headers={'Content-Type': ['application/json']},
        postdata=body,
        ).addCallbacks(ok, err)

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
    def __init__(self):
        self._handlersSp = {} # (s,p): set(handlers)

    def addSubjPredWatcher(self, func, s, p):
        if func is None:
            return
        key = s, p
        self._handlersSp.setdefault(key, set()).add(func)

    def whoCares(self, p):
        """what functions would care about the changes in this patch"""
        ret = set()
        for s in self._handlersSp.values():
            ret.update(s)
        return ret

class SyncedGraph(object):
    """
    api like rdflib.Graph which sends updates to rdfdb and can call
    you back when there are graph changes
    """
    def __init__(self, port):
        _graph = self._graph = ConjunctiveGraph()
        self._watchers = GraphWatchers()
        
        #then i try adding a statement that i will react to if i see it
        #then i print updates to that statement as they come
        #and the statement has a PID in it so we can see two clientdemos competing
        #then factor out this client, and have real light9 tools start using it to build their graphs
        #they just do full reload on relevant subgraphs at first, get progressively better
        
        def onPatch(p):
            for s in p.delGraph:
                _graph.remove(s)
            _graph.addN(p.addGraph.quads(ALLSTMTS))
            log.info("graph now has %s statements" % len(_graph))
            self.updateOnPatch(p)

        reactor.listenTCP(port, cyclone.web.Application(handlers=[
            (r'/update', makePatchEndpoint(onPatch)),
        ]))
        self.updateResource = 'http://localhost:%s/update' % port
        log.info("listening on %s" % port)
        self.register()

    def updateOnPatch(self, p):
        for func in self._watchers.whoCares(p):
            self.addHandler(func)

    def register(self):

        def done(x):
            print "registered", x.body

        cyclone.httpclient.fetch(
            url='http://localhost:8051/graphClients',
            method='POST',
            headers={'Content-Type': ['application/x-www-form-urlencoded']},
            postdata=urllib.urlencode([('clientUpdate', self.updateResource)]),
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

    # these just call through to triples() so it might be possible to
    # watch just that one
    def value(self, subj, pred):
        self._watchers.addSubjPredWatcher(self.currentFunc, subj, pred)
        return self._graph.value(subj, pred)

    def objects(self, subject=None, predicate=None):
        self._watchers.addSubjPredWatcher(self.currentFunc, subject, predicate)
        return self._graph.objects(subject, predicate)
    
