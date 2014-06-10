import re, logging
from rdflib import URIRef
from light9.namespaces import L9, RDF
from light9.curvecalc.curve import CurveResource
from light9 import Submaster, Effects
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
        self.pyResources = self._resourcesAsPython(self.resources)

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
        
    def _resourcesAsPython(self, resources):
        """
        mapping of the local names for uris in the code to high-level
        objects (Submaster, Curve)
        """
        out = {}
        subs = Submaster.get_global_submasters(self.graph)
        for localVar, uri in resources.items():
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

class EffectNode(object):
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri
        # this is not expiring at the right time, when an effect goes away
        self.graph.addHandler(self.prepare)

    def prepare(self):
        log.info("prepare effect %s", self.uri)
        # maybe there can be multiple lines of code as multiple
        # objects here, and we sort them by dependencies
        codeStrs = list(self.graph.objects(self.uri, L9['code']))
        if not codeStrs:
            raise ValueError("effect %s has no code" % self.uri)

        self.codes = [CodeLine(self.graph, s) for s in codeStrs]

        self.otherFuncs = Effects.configExprGlobals()
                
    def eval(self, songTime):
        ns = {'t': songTime}
        ns.update(self.otherFuncs)

        ns.update(dict(
            curve=lambda c, t: c.eval(t),
            ))
        # loop over lines in order, merging in outputs 
        # merge in named outputs from previous lines

        for c in self.codes:
            codeNs = ns.copy()
            codeNs.update(c.pyResources)
            if c.outName == 'out':
                out = eval(c.expr, codeNs)
        return out

