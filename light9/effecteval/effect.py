from run_local import log
import re
from rdflib import URIRef
from light9.namespaces import L9
from light9.curvecalc.curve import Curve
from light9 import Submaster

def uriFromCode(s):
    # i thought this was something a graph could do with its namespace manager
    if s.startswith('sub:'):
        return URIRef('http://light9.bigasterisk.com/show/dance2014/sub/' + s[4:])
    if s.startswith('song1:'):
        return URIRef('http://ex/effect/song1/' + s[6:])
    if (s[0], s[-1]) == ('<', '>'):
        return URIRef(s[1:-1])
    raise NotImplementedError

class EffectNode(object):
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri
        # this is not expiring at the right time, when an effect goes away
        self.graph.addHandler(self.prepare)

    def prepare(self):
        self.code = self.graph.value(self.uri, L9['code'])
        if self.code is None:
            raise ValueError("effect %s has no code" % self.uri)
        m = re.match(r'^out = sub\((.*?), intensity=(.*?)\)', self.code)
        if not m:
            raise NotImplementedError
        subUri = uriFromCode(m.group(1))
        subs = Submaster.get_global_submasters(self.graph)
        self.sub = subs.get_sub_by_uri(subUri)
        
        intensityCurve = uriFromCode(m.group(2))
        self.curve = Curve(uri=intensityCurve)

        # read from disk ok? how do we know to reread? start with
        # mtime. the mtime check could be done occasionally so on
        # average we read at most one curve's mtime per effectLoop.       

        pts = self.graph.value(intensityCurve, L9['points'])
        if pts is None:
            log.info("curve %r has no points" % intensityCurve)
        else:
            self.curve.set_from_string(pts)

        
    def eval(self, songTime):
        # consider http://waxeye.org/ for a parser that can be used in py and js
        level = self.curve.eval(songTime)
        scaledSubs = self.sub * level
        return scaledSubs
