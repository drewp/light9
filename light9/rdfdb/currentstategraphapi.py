import logging, traceback
from rdflib import ConjunctiveGraph
from light9.rdfdb.rdflibpatch import contextsForStatement as rp_contextsForStatement
log = logging.getLogger("currentstate")

class CurrentStateGraphApi(object):
    """
    mixin for SyncedGraph, separated here because these methods work together
    """

    def currentState(self, context=None, tripleFilter=(None, None, None)):
        """
        a graph you can read without being in an addHandler

        you can save some time by passing a triple filter, and we'll only give you the matching triples
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
                for s,p,o,c in self._graph.quads(tripleFilter):
                    g.store.add((s,p,o), c)

                if tripleFilter == (None, None, None):
                    self2.logThisCopy(g)
                    
                g.contextsForStatement = lambda t: contextsForStatementNoWildcards(g, t)
                return g

            def logThisCopy(self, g):
                log.info("copied graph %s statements because of this:" % len(g))
                for frame in traceback.format_stack(limit=4)[:-2]:
                    for line in frame.splitlines():
                        log.info("  "+line)

            def __exit__(self, type, val, tb):
                return

        return Mgr()

def contextsForStatementNoWildcards(g, triple):
    if None in triple:
        raise NotImplementedError("no wildcards")
    return rp_contextsForStatement(g, triple)
