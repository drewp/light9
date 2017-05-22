from rdflib import ConjunctiveGraph

from light9.rdfdb.currentstategraphapi import CurrentStateGraphApi
from light9.rdfdb.autodepgraphapi import AutoDepGraphApi
from light9.rdfdb.grapheditapi import GraphEditApi
from light9.rdfdb.rdflibpatch import patchQuads

class LocalSyncedGraph(CurrentStateGraphApi, AutoDepGraphApi, GraphEditApi):
    """for tests"""
    def __init__(self, files=None):
        self._graph = ConjunctiveGraph()
        for f in files or []:
            self._graph.parse(f, format='n3')
            

    def patch(self, p):
        patchQuads(self._graph,
                   deleteQuads=p.delQuads,
                   addQuads=p.addQuads,
                   perfect=True)
        # no deps
