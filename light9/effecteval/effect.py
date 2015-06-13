import re, logging
import toposort
from rdflib import URIRef
from light9.namespaces import L9, RDF
from light9.curvecalc.curve import CurveResource
from light9 import prof
from light9 import Submaster
from light9 import Effects # gets reload() later
log = logging.getLogger('effect')

# consider http://waxeye.org/ for a parser that can be used in py and js

class CouldNotConvert(TypeError):
    pass

class CodeLine(object):
    """code string is immutable"""
    def __init__(self, graph, code):
        self.graph, self.code = graph, code

        self.outName, self.inExpr, self.expr, self.resources = self._asPython()
        self.pyResources = self._resourcesAsPython(self.resources)
        self.possibleVars = self.findVars(self.inExpr)

    @prof.logTime
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

        def alreadyInFunc(prefix, s, i):
            return i >= len(prefix) and s[i-len(prefix):i] == prefix

        def repl(m):
            v = '_res%s' % self.uriCounter
            self.uriCounter += 1
            r = resources[v] = URIRef(m.group(1))
            for uriTypeMatches, wrapFuncName, addlArgs in [
                    (self._uriIsCurve(r), 'curve', ', t'),
                    # I'm pretty sure this shouldn't be auto-applied: it's reasonable to refer to a sub and not want its current value
                    #(self._uriIsSub(r), 'currentSubLevel', ''),
            ]:
                if uriTypeMatches:
                    if not alreadyInFunc(wrapFuncName + '(', m.string, m.start()):
                        return '%s(%s%s)' % (wrapFuncName, v, addlArgs)
            return v
        outExpr = re.sub(r'<(http\S*?)>', repl, expr)
        return lname, expr, outExpr, resources

    def findVars(self, expr):
        """may return some more strings than just the vars"""
        withoutUris = re.sub(r'<(http\S*?)>', 'None', expr)
        tokens = set(re.findall(r'\b([a-zA-Z_]\w*)\b', withoutUris))
        tokens.discard('None')
        return tokens
        
    def _uriIsCurve(self, uri):
        # this result could vary with graph changes (rare)
        return self.graph.contains((uri, RDF.type, L9['Curve']))

    def _uriIsSub(self, uri):
        return self.graph.contains((uri, RDF.type, L9['Submaster']))
        
    @prof.logTime
    def _resourcesAsPython(self, resources):
        """
        mapping of the local names for uris in the code to high-level
        objects (Submaster, Curve)
        """
        out = {}
        subs = prof.logTime(Submaster.get_global_submasters)(self.graph)
        for localVar, uri in resources.items():
            
            for rdfClass in self.graph.objects(uri, RDF.type):
                if rdfClass == L9['Curve']:
                    cr = CurveResource(self.graph, uri)
                    # this is slow- pool these curves somewhere, maybe just with curveset
                    prof.logTime(cr.loadCurve)()
                    out[localVar] = cr.curve
                    break
                elif rdfClass == L9['Submaster']:
                    out[localVar] = subs.get_sub_by_uri(uri)
                    break
                else:
                    out[localVar] = CouldNotConvert(uri)
                    break
            else:
                out[localVar] = CouldNotConvert(uri)

        return out
        
class EffectNode(object):
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri
        # this is not expiring at the right time, when an effect goes away
        self.graph.addHandler(self.prepare)

    @prof.logTime
    def prepare(self):
        log.info("prepare effect %s", self.uri)
        # maybe there can be multiple lines of code as multiple
        # objects here, and we sort them by dependencies
        codeStrs = list(self.graph.objects(self.uri, L9['code']))
        if not codeStrs:
            raise ValueError("effect %s has no code" % self.uri)

        self.codes = [CodeLine(self.graph, s) for s in codeStrs]

        self.sortCodes()

        #reload(Effects)
        self.otherFuncs = prof.logTime(Effects.configExprGlobals)()

    def sortCodes(self):
        """put self.codes in a working evaluation order"""
        codeFromOutput = dict((c.outName, c) for c in self.codes)
        deps = {}
        for c in self.codes:
            outName = c.outName
            inNames = c.possibleVars.intersection(codeFromOutput.keys())
            inNames.discard(outName)
            deps[outName] = inNames
        self.codes = [codeFromOutput[n] for n in toposort.toposort_flatten(deps)]

    def _currentSubSettingValues(self, sub):
        """what KC subSettings are setting levels right now?"""
        cs = self.graph.currentState
        with cs(tripleFilter=(None, L9['sub'], sub)) as g1:
            for subj in g1.subjects(L9['sub'], sub):
                with cs(tripleFilter=(subj, None, None)) as g2:
                    if (subj, RDF.type, L9['SubSetting']) in g2:
                        v = g2.value(subj, L9['level']).toPython()
                        yield v

    def currentSubLevel(self, uri):
        """what's the max level anyone (probably KC) is
        holding this sub to right now?"""
        if isinstance(uri, Submaster.Submaster):
            # likely the uri was spotted and replaced
            uri = uri.uri
        if not isinstance(uri, URIRef):
            raise TypeError("got %r" % uri)

        foundLevels = list(self._currentSubSettingValues(uri))
        
        if not foundLevels:
            return 0
        
        return max(foundLevels)
        
    def eval(self, songTime):
        ns = {'t': songTime}
        ns.update(self.otherFuncs)

        ns.update(dict(
            curve=lambda c, t: c.eval(t),
            currentSubLevel=self.currentSubLevel,
            ))

        for c in self.codes:
            codeNs = ns.copy()
            codeNs.update(c.pyResources)
            try:
                lineOut = eval(c.expr, codeNs)
            except Exception as e:
                e.expr = c.expr
                raise e
            ns[c.outName] = lineOut
        if 'out' not in ns:
            log.error("ran code for %s, didn't make an 'out' value", self.uri)
        return ns['out']

