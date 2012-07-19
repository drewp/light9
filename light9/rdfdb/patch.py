import json, unittest
from rdflib import ConjunctiveGraph, URIRef
from light9.rdfdb.rdflibpatch import graphFromNQuad, graphFromQuads, serializeQuad

ALLSTMTS = (None, None, None)

class Patch(object):
    """
    immutable
    
    the json representation includes the {"patch":...} wrapper
    """
    def __init__(self, jsonRepr=None, addQuads=None, delQuads=None,
                 addGraph=None, delGraph=None):
        self._jsonRepr = jsonRepr
        self._addQuads, self._delQuads = addQuads, delQuads
        self._addGraph, self._delGraph = addGraph, delGraph

        if self._jsonRepr is not None:
            body = json.loads(self._jsonRepr)
            self._delGraph = graphFromNQuad(body['patch']['deletes'])
            self._addGraph = graphFromNQuad(body['patch']['adds'])
            if 'senderUpdateUri' in body:
                self.senderUpdateUri = body['senderUpdateUri']

    @property
    def addQuads(self):
        if self._addQuads is None:
            if self._addGraph is not None:
                self._addQuads = list(self._addGraph.quads(ALLSTMTS))
            else:
                raise
        return self._addQuads

    @property
    def delQuads(self):
        if self._delQuads is None:
            if self._delGraph is not None:
                self._delQuads = list(self._delGraph.quads(ALLSTMTS))
            else:
                raise
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
