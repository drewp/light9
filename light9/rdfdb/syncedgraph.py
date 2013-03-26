from rdflib import ConjunctiveGraph, RDFS, RDF, URIRef
import logging, cyclone.httpclient, traceback, urllib, random
from itertools import chain
from twisted.internet import reactor, defer
log = logging.getLogger('syncedgraph')
from light9.rdfdb.patch import Patch
from light9.rdfdb.rdflibpatch import patchQuads, contextsForStatement as rp_contextsForStatement

# everybody who writes literals needs to get this
from rdflibpatch_literal import patch
patch()


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

    You may want to attach to self.initiallySynced deferred so you
    don't attempt patches before we've heard the initial contents of
    the graph. It would be ok to accumulate some patches of new
    material, but usually you won't correctly remove the existing
    statements unless we have the correct graph.

    If we get out of sync, we abandon our local graph (even any
    pending local changes) and get the data again from the
    server.
    """
    def __init__(self, label):
        """
        label is a string that the server will display in association
        with your connection
        """
        self.initiallySynced = defer.Deferred()
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

            if self.initiallySynced:
                self.initiallySynced.callback(None)
                self.initiallySynced = None


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
        log.info("%s add %s", [q[2] for q in p.delQuads], [q[2] for q in  p.addQuads])
        patchQuads(self._graph, p.delQuads, p.addQuads, perfect=True)
        self.updateOnPatch(p)
        self._sender.sendPatch(p).addErrback(self.sendFailed)

    def sendFailed(self, result):
        """
        we asked for a patch to be queued and sent to the master, and
        that ultimately failed because of a conflict
        """
        print "sendFailed"
        #i think we should receive back all the pending patches,
        #do a resysnc here,
        #then requeue all the pending patches (minus the failing one?) after that's done.


    def patchObject(self, context, subject, predicate, newObject):
        """send a patch which removes existing values for (s,p,*,c)
        and adds (s,p,newObject,c). Values in other graphs are not affected.

        newObject can be None, which will remove all (subj,pred,*) statements.
        """

        existing = []
        for spo in self._graph.triples((subject, predicate, None),
                                     context=context):
            existing.append(spo+(context,))
        # what layer is supposed to cull out no-op changes?
        self.patch(Patch(
            delQuads=existing,
            addQuads=([(subject, predicate, newObject, context)]
                      if newObject is not None else [])))

    def patchMapping(self, context, subject, predicate, nodeClass, keyPred, valuePred, newKey, newValue):
        """
        creates/updates a structure like this:

           ?subject ?predicate [
             a ?nodeClass;
             ?keyPred ?newKey;
             ?valuePred ?newValue ] .

        There should be a complementary readMapping that gets you a
        value since that's tricky too
        """

        with self.currentState() as graph:
            adds = set([])
            for setting in graph.objects(subject, predicate):
                if graph.value(setting, keyPred) == newKey:
                    break
            else:
                setting = URIRef(subject + "/map/%s" %
                                 random.randrange(999999999))
                adds.update([
                    (subject, predicate, setting, context),
                    (setting, RDF.type, nodeClass, context),
                    (setting, keyPred, newKey, context),
                    ])
            dels = set([])
            for prev in graph.objects(setting, valuePred):
                dels.add((setting, valuePred, prev, context))
            adds.add((setting, valuePred, newValue, context))

            if adds != dels:
                self.patch(Patch(delQuads=dels, addQuads=adds))

    def removeMappingNode(self, context, node):
        """
        removes the statements with this node as subject or object, which
        is the right amount of statements to remove a node that
        patchMapping made.
        """
        p = Patch(delQuads=[spo+(context,) for spo in
                            chain(self._graph.triples((None, None, node),
                                                      context=context),
                                  self._graph.triples((node, None, None),
                                                      context=context))])
        self.patch(p)
                
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
        if context is not None:
            raise NotImplementedError("currentState with context arg")

        class Mgr(object):
            def __enter__(self2):
                # this should be a readonly view of the existing
                # graph, maybe with something to guard against
                # writes/patches happening while reads are being
                # done. Typical usage will do some reads on this graph
                # before moving on to writes.
                
                g = ConjunctiveGraph()
                for s,p,o,c in self._graph.quads((None,None,None)):
                    g.store.add((s,p,o), c)
                g.contextsForStatement = lambda t: contextsForStatementNoWildcards(g, t)
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

    def contextsForStatement(self, triple):
        """currently this needs to be in an addHandler section, but it
        sets no watchers so it won't actually update if the statement
        was added or dropped from contexts"""
        func = self._getCurrentFunc()
        return contextsForStatementNoWildcards(self._graph, triple)

    # i find myself wanting 'patch' (aka enter/leave) versions of these calls that tell
    # you only what results have just appeared or disappeared. I think
    # I'm going to be repeating that logic a lot. Maybe just for the
    # subjects(RDF.type, t) call

def contextsForStatementNoWildcards(g, triple):
    if None in triple:
        raise NotImplementedError("no wildcards")
    return rp_contextsForStatement(g, triple)
