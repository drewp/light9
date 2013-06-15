import math, os, random, logging
from rdflib import Graph, URIRef, RDF, RDFS, Literal
from louie import dispatcher
import light9.Effects
from light9 import Submaster, showconfig, prof
from light9.Patch import get_dmx_channel
from light9.rdfdb.patch import Patch
from light9.namespaces import L9
log = logging.getLogger()

class Expr(object):
    """singleton, provides functions for use in subterm expressions,
    e.g. chases"""
    def __init__(self):
        self.effectGlobals = light9.Effects.configExprGlobals()
    
    def exprGlobals(self, startDict, t):
        """globals dict for use by expressions"""

        glo = startDict.copy()
        
        # add in functions from Effects
        glo.update(self.effectGlobals)

        glo['nsin'] = lambda x: (math.sin(x * (2 * math.pi)) + 1) / 2
        glo['ncos'] = lambda x: (math.cos(x * (2 * math.pi)) + 1) / 2
        glo['within'] = lambda a, b: a < t < b
        glo['bef'] = lambda x: t < x


        def smoove(x):
            return -2 * (x ** 3) + 3 * (x ** 2)
        glo['smoove'] = smoove

        def aft(t, x, smooth=0):
            left = x - smooth / 2
            right = x + smooth / 2
            if left < t < right:
                return smoove((t - left) / (right - left))
            return t > x
        glo['aft'] = lambda x, smooth=0: aft(t, x, smooth)

        def chan(name):
            return Submaster.Submaster(
                name=name,
                levels={get_dmx_channel(name) : 1.0})
        glo['chan'] = chan

        def smooth_random(speed=1):
            """1 = new stuff each second, <1 is slower, fade-ier"""
            x = (t * speed) % len(self._smooth_random_items)
            x1 = int(x)
            x2 = (int(x) + 1) % len(self._smooth_random_items)
            y1 = self._smooth_random_items[x1]
            y2 = self._smooth_random_items[x2]
            return y1 + (y2 - y1) * ((x - x1))

        def notch_random(speed=1):
            """1 = new stuff each second, <1 is slower, notch-ier"""
            x = (t * speed) % len(self._smooth_random_items)
            x1 = int(x)
            y1 = self._smooth_random_items[x1]
            return y1
            
        glo['noise'] = smooth_random
        glo['notch'] = notch_random

        

        return glo

exprglo = Expr()
        
class Subterm(object):
    """one Submaster and its expression evaluator"""
    def __init__(self, graph, subterm, saveContext, curveset):
        self.graph, self.uri = graph, subterm
        self.saveContext = saveContext
        self.curveset = curveset
        self.ensureExpression(saveContext)

        self._smooth_random_items = [random.random() for x in range(100)]
        self.submasters = Submaster.get_global_submasters(self.graph)
        
    def ensureExpression(self, saveCtx):
        with self.graph.currentState(tripleFilter=(self.uri, None, None)) as current:
            if current.value(self.uri, L9['expression']) is None:
                self.graph.patch(Patch(addQuads=[
                    (self.uri, L9['expression'], Literal("..."), saveCtx),
                    ]))

    def scaled(self, t):
        with self.graph.currentState(tripleFilter=(self.uri, None, None)) as current:
            subexpr_eval = self.eval(current, t)
            # we prevent any exceptions from escaping, since they cause us to
            # stop sending levels
            try:
                if isinstance(subexpr_eval, Submaster.Submaster):
                    # if the expression returns a submaster, just return it
                    return subexpr_eval
                else:
                    # otherwise, return our submaster multiplied by the value 
                    # returned
                    if subexpr_eval == 0:
                        return Submaster.Submaster("zero", {})
                    subUri = current.value(self.uri, L9['sub'])
                    sub = self.submasters.get_sub_by_uri(subUri)
                    return sub * subexpr_eval
            except Exception, e:
                dispatcher.send("expr_error", sender=self.uri, exc=repr(e))
                return Submaster.Submaster(name='Error: %s' % str(e), levels={})

    def curves_used_by_expr(self):
        """names of curves that are (maybe) used in this expression"""

        with self.graph.currentState(tripleFilter=(self.uri, None, None)) as current:
            expr = current.value(self.uri, L9['expression'])

        used = []
        for name in self.curveset.curveNamesInOrder():
            if name in expr:
                used.append(name)
        return used

    def eval(self, current, t):
        """current graph is being passed as an optimization. It should be
        equivalent to use self.graph in here."""

        objs = list(current.objects(self.uri, L9['expression']))
        if len(objs) > 1:
            raise ValueError("found multiple expressions for %s: %s" %
                             (self.uri, objs))
        
        expr = current.value(self.uri, L9['expression'])
        if not expr:
            dispatcher.send("expr_error", sender=self.uri, exc="no expr, using 0")
            return 0
        glo = self.curveset.globalsdict()
        glo['t'] = t

        glo = exprglo.exprGlobals(glo, t)
        glo['getsub'] = lambda name: self.submasters.get_sub_by_name(name)
        glo['chan'] = lambda name: Submaster.Submaster("chan", {get_dmx_channel(name): 1})
        
        try:
            self.lasteval = eval(expr, glo)
        except Exception,e:
            dispatcher.send("expr_error", sender=self.uri, exc=e)
            return Submaster.Submaster("zero", {})
        else:
            dispatcher.send("expr_error", sender=self.uri, exc="ok")
        return self.lasteval

    def __repr__(self):
        return "<Subterm %s>" % self.uri
