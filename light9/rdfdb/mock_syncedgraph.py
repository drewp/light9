
from rdflib import Graph, RDF, RDFS
from rdflib.parser import StringInputSource

class MockSyncedGraph(object):
    """
    Lets users of SyncedGraph mostly work. Doesn't yet help with any
    testing of the rerun-upon-graph-change behavior.
    """
    def __init__(self, n3Content):
        self._graph = Graph()
        self._graph.parse(StringInputSource(n3Content), format='n3')

    def addHandler(self, func):
        func()
        
    def value(self, subject=None, predicate=RDF.value, object=None,
              default=None, any=True):
        if object is not None:
            raise NotImplementedError()
        return self._graph.value(subject, predicate, object=object,
                                 default=default, any=any)

    def objects(self, subject=None, predicate=None):
        return self._graph.objects(subject, predicate)

    def label(self, uri):
        return self.value(uri, RDFS.label)

    def subjects(self, predicate=None, object=None):
        return self._graph.subjects(predicate, object)

    def predicate_objects(self, subject):
        return self._graph.predicate_objects(subject)
        
    def items(self, listUri):
        """generator. Having a chain of watchers on the results is not
        well-tested yet"""
        chain = set([listUri])
        while listUri:
            item = self.value(listUri, RDF.first)
            if item:
                yield item
            listUri = self.value(listUri, RDF.rest)
            if listUri in chain:
                raise ValueError("List contains a recursive rdf:rest reference")
            chain.add(listUri)

    def contains(self, triple):
        return triple in self._graph
