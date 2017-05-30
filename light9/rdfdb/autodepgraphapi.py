import logging
from rdflib import RDF, RDFS
from light9.rdfdb.currentstategraphapi import contextsForStatementNoWildcards
log = logging.getLogger('autodepgraphapi')

class AutoDepGraphApi(object):
    """
    knockoutjs-inspired API for automatically building a dependency
    tree while reading the graph. See addHandler().

    This design is more aggressive than knockoutjs, since the obvious
    query methods like value() all error if you're not in a watched
    section of code. This is supposed to make it easier to notice
    dependency mistakes, especially when porting old code to use
    SyncedGraph.
    
    This class is a mixin for SyncedGraph, separated here because
    these methods work together
    """

    def __init__(self):
        self._watchers = _GraphWatchers()
        self.currentFuncs = [] # stack of addHandler callers
    
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
        log.debug('graph.currentFuncs push %s', func)
        try:
            try:
                func()
            except:
                import traceback
                traceback.print_exc()
                raise
        finally:
            self.currentFuncs.pop()
            log.debug('graph.currentFuncs pop %s. stack now has %s', func, len(self.currentFuncs))

    def runDepsOnNewPatch(self, p):
        """
        patch p just happened to the graph; call everyone back who
        might care, and then notice what data they depend on now
        """
        for func in self._watchers.whoCares(p):
            # todo: forget the old handlers for this func
            log.debug('runDepsOnNewPatch calling watcher %s', p)
            self.addHandler(func)

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

    def predicate_objects(self, subject):
        func = self._getCurrentFunc()
        self._watchers.addSubjectWatcher(func, subject)
        return self._graph.predicate_objects(subject)
        
    def items(self, listUri):
        """generator. Having a chain of watchers on the results is not
        well-tested yet"""
        chain = set([listUri])
        while listUri:
            item = self.value(listUri, RDF.first)
            if item:
                yield item
            listUri = self.value(listUri, RDF.rest)
            if listUri in chain:
                raise ValueError("List contains a recursive rdf:rest reference")
            chain.add(listUri)

        
    def contains(self, triple):
        func = self._getCurrentFunc()
        self._watchers.addTripleWatcher(func, triple)
        return triple in self._graph

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


class _GraphWatchers(object):
    """
    store the current handlers that care about graph changes
    """
    def __init__(self):
        self._handlersSp = {} # (s,p): set(handlers)
        self._handlersPo = {} # (p,o): set(handlers)
        self._handlersSpo = {} # (s,p,o): set(handlers)
        self._handlersS = {} # s: set(handlers)

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

    def addTripleWatcher(self, func, triple):
        self._handlersSpo.setdefault(triple, set()).add(func)

    def addSubjectWatcher(self, func, s):
        self._handlersS.setdefault(s, set()).add(func)
        
    def whoCares(self, patch):
        """what handler functions would care about the changes in this patch?

        this removes the handlers that it gives you
        """
        #self.dependencies()
        ret = set()
        affectedSubjPreds = set([(s, p) for s, p, o, c in patch.addQuads]+
                                [(s, p) for s, p, o, c in patch.delQuads])
        for (s, p), funcs in self._handlersSp.iteritems():
            if (s, p) in affectedSubjPreds:
                ret.update(funcs)
                funcs.clear()

        affectedPredObjs = set([(p, o) for s, p, o, c in patch.addQuads]+
                                [(p, o) for s, p, o, c in patch.delQuads])
        for (p, o), funcs in self._handlersPo.iteritems():
            if (p, o) in affectedPredObjs:
                ret.update(funcs)
                funcs.clear()

        affectedTriples = set([(s, p, o) for s, p, o, c in patch.addQuads]+
                              [(s, p, o) for s, p, o, c in patch.delQuads])
        for triple, funcs in self._handlersSpo.iteritems():
            if triple in affectedTriples:
                ret.update(funcs)
                funcs.clear()
                
        affectedSubjs = set([s for s, p, o, c in patch.addQuads]+
                            [s for s, p, o, c in patch.delQuads])
        for subj, funcs in self._handlersS.iteritems():
            if subj in affectedSubjs:
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
