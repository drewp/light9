from __future__ import division
import random as random_mod
import math
import logging, colorsys
import light9.Submaster as Submaster
from chase import chase as chase_logic
import showconfig
from rdflib import RDF
from light9 import Patch
from light9.namespaces import L9
log = logging.getLogger()

registered = []
def register(f):
    registered.append(f)
    return f

@register
class Strip(object):
    """list of r,g,b tuples for sending to an LED strip"""
    which = 'L' # LR means both. W is the wide one
    pixels = []
    @classmethod
    def solid(cls, which='L', color=(1,1,1), hsv=None):
        """hsv overrides color"""
        if hsv is not None:
            color = colorsys.hsv_to_rgb(hsv[0] % 1.0, hsv[1], hsv[2])
        x = cls()
        x.which = which
        x.pixels = [tuple(color)] * 50
        return x

    def __mul__(self, f):
        if not isinstance(f, (int, float)):
            raise TypeError
            
        s = Strip()
        s.which = self.which
        s.pixels = [(r*f, g*f, b*f) for r,g,b in self.pixels]
        return s

    __rmul__ = __mul__

@register
class Blacklight(float):
    """a level for the blacklight PWM output"""
    def __mul__(self, f):
        return Blacklight(float(self) * f)
    __rmul__ = __mul__
    
@register
def chase(t, ontime=0.5, offset=0.2, onval=1.0, 
          offval=0.0, names=None, combiner=max, random=False):
    """names is list of URIs. returns a submaster that chases through
    the inputs"""
    if random:
        r = random_mod.Random(random)
        names = names[:]
        r.shuffle(names)

    chase_vals = chase_logic(t, ontime, offset, onval, offval, names, combiner)
    lev = {}
    for uri, value in chase_vals.items():
        try:
            dmx = Patch.dmx_from_uri(uri)
        except KeyError:
            log.info(("chase includes %r, which doesn't resolve to a dmx chan" %
                   uri))
            continue
        lev[dmx] = value

    return Submaster.Submaster(name="chase" ,levels=lev)

@register
def hsv(h, s, v, light='all', centerScale=.5):
    r,g,b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    lev = {}
    if light in ['left', 'all']:
        lev[73], lev[74], lev[75] = r,g,b
    if light in ['right', 'all']:
        lev[80], lev[81], lev[82] = r,g,b
    if light in ['center', 'all']:
        lev[88], lev[89], lev[90] = r*centerScale,g*centerScale,b*centerScale
    return Submaster.Submaster(name='hsv', levels=lev)
    
@register
def stack(t, names=None, fade=0):
    """names is list of URIs. returns a submaster that stacks the the inputs

    fade=0 makes steps, fade=1 means each one gets its full fraction
    of the time to fade in. Fades never...
    """
    frac = 1.0 / len(names)

    lev = {}
    for i, uri in enumerate(names):
        if t >= (i + 1) * frac:
            try:
                dmx = Patch.dmx_from_uri(uri)
            except KeyError:
                log.info(("stack includes %r, which doesn't resolve to a dmx chan"%
                       uri))
                continue
            lev[dmx] = 1
        else:
            break
    
    return Submaster.Submaster(name="stack", levels=lev)

@register
def smoove(x):
    return -2 * (x ** 3) + 3 * (x ** 2)
    
def configExprGlobals():
    graph = showconfig.getGraph()
    ret = {}

    for chaseUri in graph.subjects(RDF.type, L9['Chase']):
        shortName = chaseUri.rsplit('/')[-1]
        chans = graph.value(chaseUri, L9['channels'])
        ret[shortName] = list(graph.items(chans))
        print "%r is a chase" % shortName

    for f in registered:
        ret[f.__name__] = f

    ret['nsin'] = lambda x: (math.sin(x * (2 * math.pi)) + 1) / 2
    ret['ncos'] = lambda x: (math.cos(x * (2 * math.pi)) + 1) / 2
    def nsquare(t, on=.5):
        return (t % 1.0) < on
    ret['nsquare'] = nsquare

    _smooth_random_items = [random_mod.random() for x in range(100)]

    # suffix '2' to keep backcompat with the versions that magically knew time
    def smooth_random2(t, speed=1):
        """1 = new stuff each second, <1 is slower, fade-ier"""
        x = (t * speed) % len(_smooth_random_items)
        x1 = int(x)
        x2 = (int(x) + 1) % len(_smooth_random_items)
        y1 = _smooth_random_items[x1]
        y2 = _smooth_random_items[x2]
        return y1 + (y2 - y1) * ((x - x1))

    def notch_random2(t, speed=1):
        """1 = new stuff each second, <1 is slower, notch-ier"""
        x = (t * speed) % len(_smooth_random_items)
        x1 = int(x)
        y1 = _smooth_random_items[x1]
        return y1

    ret['noise2'] = smooth_random2
    ret['notch2'] = notch_random2



    
    return ret
