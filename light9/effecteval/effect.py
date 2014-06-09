import re, logging
from rdflib import URIRef
from light9.namespaces import L9, RDF
from light9.curvecalc.curve import CurveResource
from light9 import Submaster
log = logging.getLogger('effect')

def uriFromCode(s):
    # i thought this was something a graph could do with its namespace manager
    if s.startswith('sub:'):
        return URIRef('http://light9.bigasterisk.com/show/dance2014/sub/' + s[4:])
    if s.startswith('song1:'):
        return URIRef('http://ex/effect/song1/' + s[6:])
    if (s[0], s[-1]) == ('<', '>'):
        return URIRef(s[1:-1])
    raise NotImplementedError

# consider http://waxeye.org/ for a parser that can be used in py and js

class CodeLine(object):
    """code string is immutable"""
    def __init__(self, graph, code):
        self.graph, self.code = graph, code

        self.outName, self.expr, self.resources = self._asPython()

    def _asPython(self):
        """
        out = sub(<uri1>, intensity=<curveuri2>)
        becomes
          'out',
          'sub(_u1, intensity=curve(_u2, t))',
          {'_u1': URIRef('uri1'), '_u2': URIRef('uri2')}
        """
        lname, expr = [s.strip() for s in self.code.split('=', 1)]
        self.uriCounter = 0
        resources = {}

        def alreadyInCurveFunc(s, i):
            prefix = 'curve('
            return i >= len(prefix) and s[i-len(prefix):i] == prefix

        def repl(m):
            v = '_res%s' % self.uriCounter
            self.uriCounter += 1
            r = resources[v] = URIRef(m.group(1))
            if self._uriIsCurve(r):
                if not alreadyInCurveFunc(m.string, m.start()):
                    return 'curve(%s, t)' % v
            return v
        outExpr = re.sub(r'<(http\S*?)>', repl, expr)
        return lname, outExpr, resources

    def _uriIsCurve(self, uri):
        # this result could vary with graph changes (rare)
        return self.graph.contains((uri, RDF.type, L9['Curve']))
        
class EffectNode(object):
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri
        # this is not expiring at the right time, when an effect goes away
        self.graph.addHandler(self.prepare)

    def prepare(self):
        log.info("prepare effect %s", self.uri)
        # maybe there can be multiple lines of code as multiple
        # objects here, and we sort them by dependencies
        codeStr = self.graph.value(self.uri, L9['code'])
        if codeStr is None:
            raise ValueError("effect %s has no code" % self.uri)

        self.code = CodeLine(self.graph, codeStr)

        self.resourceMap = self.resourcesAsPython()
        
    def resourcesAsPython(self):
        """
        mapping of the local names for uris in the code to high-level
        objects (Submaster, Curve)
        """
        out = {}
        subs = Submaster.get_global_submasters(self.graph)
        for localVar, uri in self.code.resources.items():
            for rdfClass in self.graph.objects(uri, RDF.type):
                if rdfClass == L9['Curve']:
                    cr = CurveResource(self.graph, uri)
                    cr.loadCurve()
                    out[localVar] = cr.curve
                elif rdfClass == L9['Submaster']:
                    out[localVar] = subs.get_sub_by_uri(uri)
                else:
                    out[localVar] = uri

        return out
        
    def eval(self, songTime):
        ns = {'t': songTime}

        ns.update(dict(
            curve=lambda c, t: c.eval(t),
            ))
        # loop over lines in order, merging in outputs 
        # merge in named outputs from previous lines
        
        ns.update(self.resourceMap)
        return eval(self.code.expr, ns)


class GraphAwareFunction(object):
    def __init__(self, graph):
        self.graph = graph

