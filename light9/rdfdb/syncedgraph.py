from rdflib import ConjunctiveGraph, RDFS, RDF, Graph
import logging, cyclone.httpclient, traceback, urllib
from twisted.internet import reactor, defer
log = logging.getLogger('syncedgraph')
from light9.rdfdb.patch import Patch, ALLSTMTS
from light9.rdfdb.rdflibpatch import patchQuads

def sendPatch(putUri, patch, **kw):
    """
    kwargs will become extra attributes in the toplevel json object
    """
    body = patch.makeJsonRepr(kw)
    log.debug("send body: %r", body)
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
        self._handlersPo = {} # (p,o): set(handlers)

    def addSubjPredWatcher(self, func, s, p):
        if func is None:
            return
        key = s, p
        try:
            self._handlersSp.setdefault(key, set()).add(func)
        except Exception:
            log.error("with key %r and func %r" % (key, func))
            raise

    def addPredObjWatcher(self, func, p, o):
        self._handlersPo.setdefault((p, o), set()).add(func)

    def whoCares(self, patch):
        """what handler functions would care about the changes in this patch?

        this removes the handlers that it gives you
        """
        #self.dependencies()
        affectedSubjPreds = set([(s, p) for s, p, o, c in patch.addQuads]+
                                [(s, p) for s, p, o, c in patch.delQuads])
        affectedPredObjs = set([(p, o) for s, p, o, c in patch.addQuads]+
                                [(p, o) for s, p, o, c in patch.delQuads])
        
        ret = set()
        for (s, p), funcs in self._handlersSp.iteritems():
            if (s, p) in affectedSubjPreds:
                ret.update(funcs)
                funcs.clear()
                
        for (p, o), funcs in self._handlersPo.iteritems():
            if (p, o) in affectedPredObjs:
                ret.update(funcs)
                funcs.clear()

        return ret

    def dependencies(self):
        """
        for debugging, make a list of all the active handlers and what
        data they depend on. This is meant for showing on the web ui
        for browsing.
        """
        log.info("whocares:")
        from pprint import pprint
        pprint(self._handlersSp)
        

class PatchSender(object):
    """
    SyncedGraph may generate patches faster than we can send
    them. This object buffers and may even collapse patches before
    they go the server
    """
    def __init__(self, target, myUpdateResource):
        self.target = target
        self.myUpdateResource = myUpdateResource
        self._patchesToSend = []
        self._currentSendPatchRequest = None

    def sendPatch(self, p):
        sendResult = defer.Deferred()
        self._patchesToSend.append((p, sendResult))
        self._continueSending()
        return sendResult

    def _continueSending(self):
        if not self._patchesToSend or self._currentSendPatchRequest:
            return
        if len(self._patchesToSend) > 1:
            log.info("%s patches left to send", len(self._patchesToSend))
            # this is where we could concatenate little patches into a
            # bigger one. Often, many statements will cancel each
            # other out. not working yet:
            if 0:
                p = self._patchesToSend[0].concat(self._patchesToSend[1:])
                print "concat down to"
                print 'dels'
                for q in p.delQuads: print q
                print 'adds'
                for q in p.addQuads: print q
                print "----"
            else:
                p, sendResult = self._patchesToSend.pop(0)
        else:
            p, sendResult = self._patchesToSend.pop(0)
            
        self._currentSendPatchRequest = sendPatch(
            self.target, p, senderUpdateUri=self.myUpdateResource)
        self._currentSendPatchRequest.addCallbacks(self._sendPatchDone,
                                                   self._sendPatchErr)
        self._currentSendPatchRequest.chainDeferred(sendResult)

    def _sendPatchDone(self, result):
        self._currentSendPatchRequest = None
        self._continueSending()

    def _sendPatchErr(self, e):
        self._currentSendPatchRequest = None
        # we're probably out of sync with the master now, since
        # SyncedGraph.patch optimistically applied the patch to our
        # local graph already. What happens to this patch? What
        # happens to further pending patches? Some of the further
        # patches, especially, may be commutable with the bad one and
        # might still make sense to apply to the master graph.

        # if someday we are folding pending patches together, this
        # would be the time to UNDO that and attempt the original
        # separate patches again

        # this should screen for 409 conflict responses and raise a
        # special exception for that, so SyncedGraph.sendFailed can
        # screen for only that type

        # this code is going away; we're going to raise an exception that contains all the pending patches
        log.error("_sendPatchErr")
        log.error(e)
        self._continueSending()
        

class SyncedGraph(object):
    """
    graph for clients to use. Changes are synced with the master graph
    in the rdfdb process.

    This api is like rdflib.Graph but it can also call you back when
    there are graph changes to the parts you previously read.

    If we get out of sync, we abandon our local graph (even any
    pending local changes) and get the data again from the
    server.
    """
    def __init__(self, label):
        """
        label is a string that the server will display in association
        with your connection
        """
        _graph = self._graph = ConjunctiveGraph()
        self._watchers = GraphWatchers()
        
        def onPatch(p):
            """
            central server has sent us a patch
            """
            patchQuads(_graph, p.delQuads, p.addQuads, perfect=True)
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
        self.currentFuncs = [] # stack of addHandler callers
        self._sender = PatchSender('http://localhost:8051/patches',
                                   self.updateResource)

    def resync(self):
        """
        get the whole graph again from the server (e.g. we had a
        conflict while applying a patch and want to return to the
        truth).

        To avoid too much churn, we remember our old graph and diff it
        against the replacement. This way, our callers only see the
        corrections.

        Edits you make during a resync will surely be lost, so I
        should just fail them. There should be a notification back to
        UIs who want to show that we're doing a resync.
        """
        return cyclone.httpclient.fetch(
            url="http://localhost:8051/graph",
            method="GET",
            headers={'Accept':'x-trig'},
            ).addCallback(self._resyncGraph)

    def _resyncGraph(self, response):
        pass
        #diff against old entire graph
        #broadcast that change

    def register(self, label):

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

    def patch(self, p):
        """send this patch to the server and apply it to our local
        graph and run handlers"""

        # these could fail if we're out of sync. One approach:
        # Rerequest the full state from the server, try the patch
        # again after that, then give up.
        
        patchQuads(self._graph, p.delQuads, p.addQuads, perfect=True)
        self.updateOnPatch(p)
        self._sender.sendPatch(p).addErrback(self.sendFailed)

    def sendFailed(self, result):
        """
        we asked for a patch to be queued and sent to the master, and
        that ultimately failed because of a conflict
        """
        #i think we should receive back all the pending patches,
        #do a resysnc here,
        #then requeue all the pending patches (minus the failing one?) after that's done.


    def patchObject(self, context, subject, predicate, newObject):
        """send a patch which removes existing values for (s,p,*,c)
        and adds (s,p,newObject,c). Values in other graphs are not affected"""

        existing = []
        for spo in self._graph.triples((subject, predicate, None),
                                     context=context):
            existing.append(spo+(context,))
        # what layer is supposed to cull out no-op changes?
        self.patch(Patch(
            delQuads=existing,
            addQuads=[(subject, predicate, newObject, context)]))

    def patchMapping(self, context, subject, predicate, keyPred, valuePred, newKey, newValue):
        """
        proposed api for updating things like ?session :subSetting [
        :sub ?s; :level ?v ]. Keyboardcomposer has an implementation
        already. There should be a complementary readMapping that gets
        you a value since that's tricky too
        """

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

        self.currentFuncs.append(func)
        try:
            func()
        finally:
            self.currentFuncs.pop()

    def updateOnPatch(self, p):
        """
        patch p just happened to the graph; call everyone back who
        might care, and then notice what data they depend on now
        """
        for func in self._watchers.whoCares(p):
            # todo: forget the old handlers for this func
            self.addHandler(func)

    def currentState(self, context=None):
        """
        a graph you can read without being in an addHandler
        """
        class Mgr(object):
            def __enter__(self2):
                # this should be a readonly view of the existing graph
                g = Graph()
                for s in self._graph.triples((None, None, None), context):
                    g.add(s)
                return g
            
            def __exit__(self, type, val, tb):
                return

        return Mgr()

    def _getCurrentFunc(self):
        if not self.currentFuncs:
            # this may become a warning later
            raise ValueError("asked for graph data outside of a handler")

        # we add the watcher to the deepest function, since that
        # should be the cheapest way to update when this part of the
        # data changes
        return self.currentFuncs[-1]

    # these just call through to triples() so it might be possible to
    # watch just that one.

    # if you get a bnode in your response, maybe the answer to
    # dependency tracking is to say that you depended on the triple
    # that got you that bnode, since it is likely to change to another
    # bnode later. This won't work if the receiver stores bnodes
    # between calls, but probably most of them don't do that (they
    # work from a starting uri)
    
    def value(self, subject=None, predicate=RDF.value, object=None,
              default=None, any=True):
        if object is not None:
            raise NotImplementedError()
        func = self._getCurrentFunc()
        self._watchers.addSubjPredWatcher(func, subject, predicate)
        return self._graph.value(subject, predicate, object=object,
                                 default=default, any=any)

    def objects(self, subject=None, predicate=None):
        func = self._getCurrentFunc()
        self._watchers.addSubjPredWatcher(func, subject, predicate)
        return self._graph.objects(subject, predicate)
    
    def label(self, uri):
        return self.value(uri, RDFS.label)

    def subjects(self, predicate=None, object=None):
        func = self._getCurrentFunc()
        self._watchers.addPredObjWatcher(func, predicate, object)
        return self._graph.subjects(predicate, object)

    # i find myself wanting 'patch' versions of these calls that tell
    # you only what results have just appeared or disappeared. I think
    # I'm going to be repeating that logic a lot. Maybe just for the
    # subjects(RDF.type, t) call
