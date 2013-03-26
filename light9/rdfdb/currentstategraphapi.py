from rdflib import ConjunctiveGraph
from light9.rdfdb.rdflibpatch import contextsForStatement as rp_contextsForStatement

class CurrentStateGraphApi(object):
    
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

def contextsForStatementNoWildcards(g, triple):
    if None in triple:
        raise NotImplementedError("no wildcards")
    return rp_contextsForStatement(g, triple)
