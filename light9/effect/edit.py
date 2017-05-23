import json
import cyclone.httpclient
from twisted.internet.defer import inlineCallbacks, returnValue
from rdflib import URIRef, Literal

from light9 import networking
from light9.namespaces import L9, RDF, RDFS
from light9.rdfdb.patch import Patch
from light9.curvecalc.curve import CurveResource

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


@inlineCallbacks
def getMusicStatus():
    returnValue(json.loads((yield cyclone.httpclient.fetch(
        networking.musicPlayer.path('time'), timeout=.5)).body))

@inlineCallbacks
def songEffectPatch(graph, dropped, song, event, ctx):
    """
    some uri was 'dropped' in the timeline. event is 'default' or 'start' or 'end'.
    """
    with graph.currentState(
            tripleFilter=(dropped, None, None)) as g:
        droppedTypes = list(g.objects(dropped, RDF.type))
        droppedLabel = g.label(dropped)
        droppedCodes = list(g.objects(dropped, L9['code']))

    quads = []
    fade = 2 if event == 'default' else 0

    if _songHasEffect(graph, song, dropped):
        # bump the existing curve
        pass
    else:
        effect, q = _newEffect(graph, song, ctx)
        quads.extend(q)

        curve = graph.sequentialUri(song + "/curve-")
        yield _newEnvelopeCurve(graph, ctx, curve, droppedLabel, fade)
        quads.extend([
            (song, L9['curve'], curve, ctx),
            (effect, RDFS.label, droppedLabel, ctx),
            (effect, L9['code'], Literal('env = %s' % curve.n3()), ctx),
            ])

        if L9['EffectClass'] in droppedTypes:
            quads.extend([
                (effect, RDF.type, dropped, ctx),
                ] + [(effect, L9['code'], c, ctx) for c in droppedCodes])
        elif L9['Submaster'] in droppedTypes:
            quads.extend([
                (effect, L9['code'], Literal('out = %s * env' % dropped.n3()),
                 ctx),
                ])
        else:
            raise NotImplementedError(
                "don't know how to add an effect from %r (types=%r)" %
                (dropped, droppedTypes))

        _maybeAddMusicLine(quads, effect, song, ctx)

    print "adding"
    for qq in quads:
        print qq
    returnValue(Patch(addQuads=quads))
    

    
def _songHasEffect(graph, song, uri):
    """does this song have an effect of class uri or a sub curve for sub
    uri? this should be simpler to look up."""
    return False # todo

def musicCurveForSong(uri):
    return URIRef(uri + 'music')
    
def _newEffect(graph, song, ctx):
    effect = graph.sequentialUri(song + "/effect-")
    quads = [
        (song, L9['effect'], effect, ctx),
        (effect, RDF.type, L9['Effect'], ctx),
    ]
    print "_newEffect", effect, quads
    return effect, quads
    
@inlineCallbacks
def _newEnvelopeCurve(graph, ctx, uri, label, fade=2):
    """this does its own patch to the graph"""
    
    cr = CurveResource(graph, uri)
    cr.newCurve(ctx, label=Literal(label))
    yield _insertEnvelopePoints(cr.curve, fade)
    cr.saveCurve()

@inlineCallbacks
def _insertEnvelopePoints(curve, fade=2):
    # wrong: we might not be adding to the currently-playing song.
    musicStatus = yield getMusicStatus()
    songTime=musicStatus['t']
    songDuration=musicStatus['duration']
    
    t1 = clamp(songTime - fade, .1, songDuration - .1 * 2) + fade
    t2 = clamp(songTime + 20, t1 + .1, songDuration)
    
    curve.insert_pt((t1 - fade, 0))
    curve.insert_pt((t1, 1))
    curve.insert_pt((t2, 1))
    curve.insert_pt((t2 + fade, 0))
    
    
def _maybeAddMusicLine(quads, effect, song, ctx):
    """
    add a line getting the current music into 'music' if any code might
    be mentioning that var
    """
    
    for spoc in quads:
        if spoc[1] == L9['code'] and 'music' in spoc[2]:
            quads.extend([
                (effect, L9['code'],
                 Literal('music = %s' % musicCurveForSong(song).n3()), ctx)
                ])
            break
