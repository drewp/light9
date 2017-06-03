import unittest
import mock
import tempfile
from rdflib import URIRef, Graph
from light9.rdfdb.graphfile import GraphFile

class TestGraphFileOutput(unittest.TestCase):
    def testMaintainsN3PrefixesFromInput(self):
        tf = tempfile.NamedTemporaryFile(suffix='_test.n3')
        tf.write('''
        @prefix : <http://example.com/> .
        @prefix n: <http://example.com/n/> .
        :foo n:bar :baz .
        ''')
        tf.flush()

        def getSubgraph(uri):
            return Graph()
        gf = GraphFile(mock.Mock(), tf.name, URIRef('uri'), mock.Mock(), getSubgraph, {}, {})
        gf.reread()
        
        newGraph = Graph()
        newGraph.add((URIRef('http://example.com/boo'),
                      URIRef('http://example.com/n/two'),
                      URIRef('http://example.com/other/ns')))
        gf.dirty(newGraph)
        gf.flush()
        wroteContent = open(tf.name).read()
        self.assertEqual('''@prefix : <http://example.com/> .
@prefix n: <http://example.com/n/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xml: <http://www.w3.org/XML/1998/namespace> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:boo n:two <http://example.com/other/ns> .
''', wroteContent)
