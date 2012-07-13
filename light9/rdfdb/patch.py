import json
from rdflib import ConjunctiveGraph

ALLSTMTS = (None, None, None)

def graphFromQuads(q):
    g = ConjunctiveGraph()
    #g.addN(q) # no effect on nquad output
    for s,p,o,c in q:
        g.get_context(c).add((s,p,o))
        #g.store.add((s,p,o), c) # no effect on nquad output
    return g

class Patch(object):
    """
    the json representation includes the {"patch":...} wrapper
    """
    def __init__(self, jsonRepr=None, addQuads=None, delQuads=None,
                 addGraph=None, delGraph=None):
        self._jsonRepr = jsonRepr
        self._addQuads, self._delQuads = addQuads, delQuads
        self._addGraph, self._delGraph = addGraph, delGraph

        if self._jsonRepr is not None:
            body = json.loads(self._jsonRepr)
            self._delGraph = ConjunctiveGraph()
            self._delGraph.parse(data=body['patch']['deletes'], format='nquads')
            self._addGraph = ConjunctiveGraph()
            self._addGraph.parse(data=body['patch']['adds'], format='nquads')

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
            self._jsonRepr = json.dumps({"patch": {
                'adds':self.addGraph.serialize(format='nquads'),
                'deletes':self.delGraph.serialize(format='nquads'),
                }})
        return self._jsonRepr
