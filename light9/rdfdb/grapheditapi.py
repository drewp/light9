import random, logging
from itertools import chain
from rdflib import URIRef, RDF
from light9.rdfdb.patch import Patch, quadsWithContextUris
log = logging.getLogger('graphedit')

class GraphEditApi(object):
    """
    fancier graph edits
    
    mixin for SyncedGraph, separated here because these methods work together
    """

    def getObjectPatch(self, context, subject, predicate, newObject):
        """send a patch which removes existing values for (s,p,*,c)
        and adds (s,p,newObject,c). Values in other graphs are not affected.

        newObject can be None, which will remove all (subj,pred,*) statements.
        """

        existing = []
        for spo in self._graph.triples((subject, predicate, None),
                                     context=context):
            existing.append(spo+(context,))
        # what layer is supposed to cull out no-op changes?
        return Patch(
            delQuads=existing,
            addQuads=([(subject, predicate, newObject, context)]
                      if newObject is not None else []))

    def patchObject(self, context, subject, predicate, newObject):
        p = self.getObjectPatch(context, subject, predicate, newObject)
        log.info("patchObject %r" % p.jsonRepr)
        self.patch(p)

    def patchSubgraph(self, context, newGraph):
        """
        replace all statements in 'context' with the quads in newGraph.
        This is not cooperating with currentState.
        """
        old = set(quadsWithContextUris(self._graph.quads((None, None, None, context))))
        new = set(quadsWithContextUris(newGraph))
        p = Patch(delQuads=old - new, addQuads=new - old)
        self.patch(p)
        
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

        # as long as currentState is expensive and has the
        # tripleFilter optimization, this looks like a mess. If
        # currentState became cheap, a lot of code here could go away.
        
        with self.currentState(tripleFilter=(subject, predicate, None)) as current:
            adds = set([])
            for setting in current.objects(subject, predicate):
                with self.currentState(tripleFilter=(setting, keyPred, None)) as current2:
                
                    match = current2.value(setting, keyPred) == newKey
                if match:
                    break
            else:
                setting = URIRef(subject + "/map/%s" %
                                 random.randrange(999999999))
                adds.update([
                    (subject, predicate, setting, context),
                    (setting, RDF.type, nodeClass, context),
                    (setting, keyPred, newKey, context),
                    ])

        with self.currentState(tripleFilter=(setting, valuePred, None)) as current:
            dels = set([])
            for prev in current.objects(setting, valuePred):
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

import unittest
from rdflib import ConjunctiveGraph
class TestPatchSubgraph(unittest.TestCase):
    def testCollapsesIdenticalQuads(self):
        appliedPatches = []
        class Obj(GraphEditApi):
            def patch(self, p):
                appliedPatches.append(p)
        obj = Obj()
        obj._graph = ConjunctiveGraph()
        stmt1 = (URIRef('s'), URIRef('p'), URIRef('o'), URIRef('g'))
        obj._graph.addN([stmt1])
        obj.patchSubgraph(URIRef('g'), [stmt1])
        self.assertEqual(len(appliedPatches), 1)
        p = appliedPatches[0]
        self.assert_(p.isNoop())
        self.assertEqual(p.jsonRepr, '{"patch": {"adds": "", "deletes": ""}}')
