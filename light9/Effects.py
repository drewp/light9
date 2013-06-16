from __future__ import division
from random import Random
import logging, colorsys
import light9.Submaster as Submaster
from chase import chase as chase_logic
import showconfig
from rdflib import RDF
from light9 import Patch
from light9.namespaces import L9
log = logging.getLogger()

def chase(t, ontime=0.5, offset=0.2, onval=1.0, 
          offval=0.0, names=None, combiner=max, random=False):
    """names is list of URIs. returns a submaster that chases through
    the inputs"""
    if random:
        r = Random(random)
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

def configExprGlobals():
    graph = showconfig.getGraph()
    ret = {}

    for chaseUri in graph.subjects(RDF.type, L9['Chase']):
        shortName = chaseUri.rsplit('/')[-1]
        chans = graph.value(chaseUri, L9['channels'])
        ret[shortName] = list(graph.items(chans))
        print "%r is a chase" % shortName

    ret['chase'] = chase
    ret['stack'] = stack
    ret['hsv'] = hsv
    return ret
