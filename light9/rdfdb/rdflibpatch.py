"""
this is a proposal for a ConjunctiveGraph method in rdflib
"""

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

import unittest
from rdflib import ConjunctiveGraph, URIRef as U
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
        
