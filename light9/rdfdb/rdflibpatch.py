"""
this is a proposal for a ConjunctiveGraph method in rdflib
"""
import unittest
from rdflib import ConjunctiveGraph, URIRef as U

def patchQuads(graph, deleteQuads, addQuads, perfect=False):
    """
    Delete the sequence of given quads. Then add the given quads just
    like addN would. If perfect is True, we'll error and not touch the
    graph if any of the deletes isn't in the graph or if any of the
    adds was already in the graph.
    """
    toDelete = []
    for s, p, o, c in deleteQuads:
        stmt = (s, p, o)
        if perfect:
            if not any(graph.store.triples(stmt, c)):
                raise ValueError("%r not in %r" % (stmt, c))
            else:
                toDelete.append((c, stmt))
        else:
            graph.store.remove(stmt, context=c)
    for c, stmt in toDelete:
        graph.store.remove(stmt, context=c)

    if perfect:
        addQuads = list(addQuads)
        for spoc in addQuads:
            if spoc in graph:
                raise ValueError("%r already in %r" % (spoc[:3], spoc[3]))
    graph.addN(addQuads)



def graphFromQuads(q):
    g = ConjunctiveGraph()
    #g.addN(q) # no effect on nquad output
    for s,p,o,c in q:
        #g.get_context(c).add((s,p,o)) # kind of works with broken rdflib nquad serializer code
        g.store.add((s,p,o), c) # no effect on nquad output
    return g

def graphFromNQuad(text):
    """
    g.parse(data=self.nqOut, format='nquads')
    makes a graph that serializes to nothing
    """
    g1 = ConjunctiveGraph()
    g1.parse(data=text, format='nquads')
    g2 = ConjunctiveGraph()
    for s,p,o,c in g1.quads((None,None,None)):
        #g2.get_context(c).add((s,p,o))
        g2.store.add((s,p,o), c)
    #import pprint; pprint.pprint(g2.store.__dict__)
    return g2

from rdflib.plugins.serializers.nt import _xmlcharref_encode
def serializeQuad(g):
    """replacement for graph.serialize(format='nquads')"""
    out = ""
    for s,p,o,c in g.quads((None,None,None)):
        out += u"%s %s %s %s .\n" % (s.n3(),
                                p.n3(),
                                _xmlcharref_encode(o.n3()), 
                                c.n3())
    return out

class TestGraphFromQuads(unittest.TestCase):
    nqOut = '<http://example.com/> <http://example.com/> <http://example.com/> <http://example.com/> .\n'
    def testSerializes(self):
        n = U("http://example.com/")
        g = graphFromQuads([(n,n,n,n)])
        out = serializeQuad(g)
        self.assertEqual(out.strip(), self.nqOut.strip())

    def testNquadParserSerializes(self):
        g = graphFromNQuad(self.nqOut)
        self.assertEqual(len(g), 1)
        out = serializeQuad(g)
        self.assertEqual(out.strip(), self.nqOut.strip())
        


stmt1 = U('http://a'), U('http://b'), U('http://c'), U('http://ctx1')
stmt2 = U('http://a'), U('http://b'), U('http://c'), U('http://ctx2')
class TestPatchQuads(unittest.TestCase):
    def testAddsToNewContext(self):
        g = ConjunctiveGraph()
        patchQuads(g, [], [stmt1])
        self.assert_(len(g), 1)
        quads = list(g.quads((None,None,None)))
        self.assertEqual(quads, [stmt1])

    def testDeletes(self):
        g = ConjunctiveGraph()
        patchQuads(g, [], [stmt1])
        patchQuads(g, [stmt1], [])
        quads = list(g.quads((None,None,None)))
        self.assertEqual(quads, [])

    def testDeleteRunsBeforeAdd(self):
        g = ConjunctiveGraph()
        patchQuads(g, [stmt1], [stmt1])
        quads = list(g.quads((None,None,None)))
        self.assertEqual(quads, [stmt1])
        
    def testPerfectAddRejectsExistingStmt(self):
        g = ConjunctiveGraph()
        patchQuads(g, [], [stmt1])
        self.assertRaises(ValueError, patchQuads, g, [], [stmt1], perfect=True)

    def testPerfectAddAllowsExistingStmtInNewContext(self):
        g = ConjunctiveGraph()
        patchQuads(g, [], [stmt1])
        patchQuads(g, [], [stmt2], perfect=True)
        self.assertEqual(len(list(g.quads((None,None,None)))), 2)

    def testPerfectDeleteRejectsAbsentStmt(self):
        g = ConjunctiveGraph()
        self.assertRaises(ValueError, patchQuads, g, [stmt1], [], perfect=True)
        
    def testPerfectDeleteAllowsRemovalOfStmtInMultipleContexts(self):
        g = ConjunctiveGraph()
        patchQuads(g, [], [stmt1, stmt2])
        patchQuads(g, [stmt1], [], perfect=True)

    def testRedundantStmtOkForAddOrDelete(self):
        g = ConjunctiveGraph()
        patchQuads(g, [], [stmt1, stmt1], perfect=True)
        patchQuads(g, [stmt1, stmt1], [], perfect=True)
        
