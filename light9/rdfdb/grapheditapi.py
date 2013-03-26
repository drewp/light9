import random
from itertools import chain
from rdflib import URIRef, RDF
from light9.rdfdb.patch import Patch

class GraphEditApi(object):
    """
    mixin for SyncedGraph, separated here because these methods work together
    """

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
