import unittest
import mock
import sys
sys.path.insert(0, 'bin')  # for run_local

from .effect import CodeLine
from rdflib import URIRef


def isCurve(self, uri):
    return 'curve' in uri


def isSub(self, uri):
    return 'sub' in uri


@mock.patch('light9.effecteval.effect.CodeLine._uriIsCurve', new=isCurve)
@mock.patch('light9.effecteval.effect.CodeLine._uriIsSub', new=isSub)
@mock.patch('light9.effecteval.effect.CodeLine._resourcesAsPython',
            new=lambda self, r: self.expr)
class TestAsPython(unittest.TestCase):

    def test_gets_lname(self):
        ec = CodeLine(graph=None, code='x = y+1')
        self.assertEqual('x', ec.outName)

    def test_gets_simple_code(self):
        ec = CodeLine(graph=None, code='x = y+1')
        self.assertEqual('y+1', ec._asPython()[2])
        self.assertEqual({}, ec._asPython()[3])

    def test_converts_uri_to_var(self):
        ec = CodeLine(graph=None, code='x = <http://example.com/>')
        _, inExpr, expr, uris = ec._asPython()
        self.assertEqual('_res0', expr)
        self.assertEqual({'_res0': URIRef('http://example.com/')}, uris)

    def test_converts_multiple_uris(self):
        ec = CodeLine(graph=None,
                      code='x = <http://example.com/> + <http://other>')
        _, inExpr, expr, uris = ec._asPython()
        self.assertEqual('_res0 + _res1', expr)
        self.assertEqual(
            {
                '_res0': URIRef('http://example.com/'),
                '_res1': URIRef('http://other')
            }, uris)

    def test_doesnt_fall_for_brackets(self):
        ec = CodeLine(graph=None, code='x = 1<2>3< h')
        _, inExpr, expr, uris = ec._asPython()
        self.assertEqual('1<2>3< h', expr)
        self.assertEqual({}, uris)

    def test_curve_uri_expands_to_curve_eval_func(self):
        ec = CodeLine(graph=None, code='x = <http://example/curve1>')
        _, inExpr, expr, uris = ec._asPython()
        self.assertEqual('curve(_res0, t)', expr)
        self.assertEqual({'_res0': URIRef('http://example/curve1')}, uris)

    def test_curve_doesnt_double_wrap(self):
        ec = CodeLine(graph=None,
                      code='x = curve(<http://example/curve1>, t+.01)')
        _, inExpr, expr, uris = ec._asPython()
        self.assertEqual('curve(_res0, t+.01)', expr)
        self.assertEqual({'_res0': URIRef('http://example/curve1')}, uris)


@mock.patch('light9.effecteval.effect.CodeLine._uriIsCurve', new=isCurve)
@mock.patch('light9.effecteval.effect.CodeLine._resourcesAsPython',
            new=lambda self, r: self.expr)
class TestPossibleVars(unittest.TestCase):

    def test1(self):
        self.assertEqual(set([]), CodeLine(None, 'a1 = 1').possibleVars)

    def test2(self):
        self.assertEqual({'a2'}, CodeLine(None, 'a1 = a2').possibleVars)

    def test3(self):
        self.assertEqual({'a2', 'a3'},
                         CodeLine(None, 'a1 = a2 + a3').possibleVars)
