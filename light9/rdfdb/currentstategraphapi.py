import logging, traceback, time, itertools
from rdflib import ConjunctiveGraph
from light9.rdfdb.rdflibpatch import contextsForStatement as rp_contextsForStatement
log = logging.getLogger("currentstate")

class ReadOnlyConjunctiveGraph(object):
    """similar to rdflib's ReadOnlyGraphAggregate but takes one CJ in, instead
    of a bunch of Graphs"""
    def __init__(self, graph):
        self.graph = graph

    def __getattr__(self, attr):
        if attr in ['subjects', 'value', 'objects', 'triples', 'label']: # not complete
            return getattr(self.graph, attr)
        raise TypeError("can't access %r of read-only graph" % attr)

    def __len__(self):
        return len(self.graph)


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

                if 1:
                    g = ReadOnlyConjunctiveGraph(self._graph)
                else:
                    t1 = time.time()
                    g = ConjunctiveGraph()
                    for s,p,o,c in self._graph.quads(tripleFilter):
                        g.store.add((s,p,o), c)

                    if tripleFilter == (None, None, None):
                        self2.logThisCopy(g, time.time() - t1)
                    
                g.contextsForStatement = lambda t: contextsForStatementNoWildcards(g, t)
                return g

            def logThisCopy(self, g, sec):
                log.info("copied graph %s statements (%.1f ms) "
                         "because of this:" % (len(g), sec * 1000))
                for frame in traceback.format_stack(limit=4)[:-2]:
                    for line in frame.splitlines():
                        log.info("  "+line)

            def __exit__(self, type, val, tb):
                return

        return Mgr()

    def sequentialUri(self, prefix):
        """
        Prefix URIRef like http://example.com/r- will return
        http://example.com/r-1 if that uri is not a subject in the graph,
        or else http://example.com/r-2, etc
        """
        for i in itertools.count(1):
            newUri = prefix + str(i)
            if not list(self._graph.triples((newUri, None, None))) and newUri not in getattr(self, '_reservedSequentials', []):
                if not hasattr(self, '_reservedSequentials'):
                    self._reservedSequentials = set()
                self._reservedSequentials.add(newUri)
                return newUri

        
def contextsForStatementNoWildcards(g, triple):
    if None in triple:
        raise NotImplementedError("no wildcards")
    return rp_contextsForStatement(g, triple)
