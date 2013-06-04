import json, unittest
from rdflib import ConjunctiveGraph, Graph, URIRef, URIRef as U
from light9.rdfdb.rdflibpatch import graphFromNQuad, graphFromQuads, serializeQuad

ALLSTMTS = (None, None, None)

def quadsWithContextUris(quads):
    """
    yield the given quads, correcting any context values that are
    Graphs into URIRefs
    """
    for s,p,o,c in quads:
        if isinstance(c, Graph):
            c = c.identifier
        if not isinstance(c, URIRef):
            raise TypeError("bad quad context type in %r" % ((s,p,o,c),))
        yield s,p,o,c

class Patch(object):
    """
    immutable
    
    the json representation includes the {"patch":...} wrapper
    """
    def __init__(self, jsonRepr=None, addQuads=None, delQuads=None,
                 addGraph=None, delGraph=None):
        """
        addQuads/delQuads can be lists or sets, but if we make them internally,
        they'll be lists

        4th element of a quad must be a URIRef
        """
        self._jsonRepr = jsonRepr
        self._addQuads, self._delQuads = addQuads, delQuads
        self._addGraph, self._delGraph = addGraph, delGraph

        if self._jsonRepr is not None:
            body = json.loads(self._jsonRepr)
            self._delGraph = graphFromNQuad(body['patch']['deletes'])
            self._addGraph = graphFromNQuad(body['patch']['adds'])
            if 'senderUpdateUri' in body:
                self.senderUpdateUri = body['senderUpdateUri']
                
    @classmethod
    def fromDiff(cls, oldGraph, newGraph):
        """
        make a patch that changes oldGraph to newGraph
        """
        old = set(quadsWithContextUris(oldGraph.quads(ALLSTMTS)))
        new = set(quadsWithContextUris(newGraph.quads(ALLSTMTS)))
        return cls(addQuads=list(new - old), delQuads=list(old - new))

    def __nonzero__(self):
        """
        does this patch do anything to a graph?
        """
        if self._jsonRepr and self._jsonRepr.strip():
            raise NotImplementedError()
        return bool(self._addQuads or self._delQuads or
                    self._addGraph or self._delGraph)

    @property
    def addQuads(self):
        if self._addQuads is None:
            if self._addGraph is None:
                return []
            self._addQuads = list(quadsWithContextUris(
                self._addGraph.quads(ALLSTMTS)))
        return self._addQuads

    @property
    def delQuads(self):
        if self._delQuads is None:
            if self._delGraph is None:
                return []
            self._delQuads = list(quadsWithContextUris(
                self._delGraph.quads(ALLSTMTS)))
        return self._delQuads

    @property
    def addGraph(self):
        if self._addGraph is None:
            self._addGraph = graphFromQuads(self._addQuads)
        return self._addGraph

    @property
    def delGraph(self):
        if self._delGraph is None:
            self._delGraph = graphFromQuads(self._delQuads)
        return self._delGraph

    @property
    def jsonRepr(self):
        if self._jsonRepr is None:
            self._jsonRepr = self.makeJsonRepr()
        return self._jsonRepr

    def makeJsonRepr(self, extraAttrs={}):
        d = {"patch" : {
            'adds' : serializeQuad(self.addGraph),
            'deletes' : serializeQuad(self.delGraph),
            }}
        if len(self.addGraph) > 0 and d['patch']['adds'].strip() == "":
            # this is the bug that graphFromNQuad works around
            raise ValueError("nquads serialization failure")
        if '[<' in d['patch']['adds']:
            raise ValueError("[< found in %s" % d['patch']['adds'])
        d.update(extraAttrs)
        return json.dumps(d)

    def concat(self, more):
        """
        new Patch with the result of applying this patch and the
        sequence of other Patches
        """
        # not working yet
        adds = set(self.addQuads)
        dels = set(self.delQuads)
        for p2 in more:
            for q in p2.delQuads:
                if q in adds:
                    adds.remove(q)
                else:
                    dels.add(q)
            for q in p2.addQuads:
                if q in dels:
                    dels.remove(q)
                else:
                    adds.add(q)
        return Patch(delQuads=dels, addQuads=adds)

    def getContext(self):
        """assumes that all the edits are on the same context"""
        ctx = None
        for q in self.addQuads + self.delQuads:
            if ctx is None:
                ctx = q[3]

            if ctx != q[3]:
                raise ValueError("patch applies to multiple contexts, at least %r and %r" % (ctx, q[3]))
        if ctx is None:
            raise ValueError("patch affects no contexts")
        assert isinstance(ctx, URIRef), ctx
        return ctx

stmt1 = U('http://a'), U('http://b'), U('http://c'), U('http://ctx1')

class TestPatchFromDiff(unittest.TestCase):
    def testEmpty(self):
        g = ConjunctiveGraph()
        p = Patch.fromDiff(g, g)
        self.assert_(not p)

    def testNonEmpty(self):
        g1 = ConjunctiveGraph()
        g2 = graphFromQuads([stmt1])
        p = Patch.fromDiff(g1, g2)
        self.assert_(p)

    def testNoticesAdds(self):
        g1 = ConjunctiveGraph()
        g2 = graphFromQuads([stmt1])
        p = Patch.fromDiff(g1, g2)
        self.assertEqual(p.addQuads, [stmt1])
        self.assertEqual(p.delQuads, [])

    def testNoticesDels(self):
        g1 = graphFromQuads([stmt1])
        g2 = ConjunctiveGraph()
        p = Patch.fromDiff(g1, g2)
        self.assertEqual(p.addQuads, [])
        self.assertEqual(p.delQuads, [stmt1])
        
        
class TestPatchGetContext(unittest.TestCase):
    def testEmptyPatchCantGiveContext(self):
        p = Patch()
        self.assertRaises(ValueError, p.getContext)

    def testSimplePatchReturnsContext(self):
        p = Patch(addQuads=[stmt1])
        self.assertEqual(p.getContext(), U('http://ctx1'))

    def testMultiContextPatchFailsToReturnContext(self):
        p = Patch(addQuads=[stmt1[:3] + (U('http://ctx1'),),
                            stmt1[:3] + (U('http://ctx2'),)])
        self.assertRaises(ValueError, p.getContext)
                  
