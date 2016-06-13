from __future__ import division
from rdflib import URIRef, Literal
from light9.namespaces import L9, RDF
from webcolors import rgb_to_hex, hex_to_rgb
from decimal import Decimal
import math
from noise import pnoise1
import logging

log = logging.getLogger('effecteval')

def literalColor(rnorm, gnorm, bnorm):
    return Literal(rgb_to_hex([rnorm * 255, gnorm * 255, bnorm * 255]))

def nsin(x): return (math.sin(x * (2 * math.pi)) + 1) / 2
def ncos(x): return (math.cos(x * (2 * math.pi)) + 1) / 2
def nsquare(t, on=.5):
    return (t % 1.0) < on
def lerp(a, b, t):
    return a + (b - a) * t
def noise(t):
    return pnoise1(t, 2)

def scale(value, strength):
    if isinstance(value, Literal):
        value = value.toPython()

    if isinstance(value, Decimal):
        value = float(value)
        
    if isinstance(value, basestring):
        if value[0] == '#':
            r,g,b = hex_to_rgb(value)
            if isinstance(strength, Literal):
                strength = strength.toPython()
            if isinstance(strength, basestring):
                sr, sg, sb = [v/255 for v in hex_to_rgb(strength)]
            else:
                sr = sg = sb = strength
            return rgb_to_hex([int(r * sr), int(g * sg), int(b * sb)])
    elif isinstance(value, (int, float)):
        return value * strength
    else:
        raise NotImplementedError(repr(value))
    
class EffectEval(object):
    """
    runs one effect's code to turn effect attr settings into output
    device settings. No state; suitable for reload().
    """
    def __init__(self, graph, effect, sharedEffectOutputs):
        self.graph = graph
        self.effect = effect 

        # effect : [(dev, attr, value, isScaled)]
        self.effectOutputs = sharedEffectOutputs

        if not self.effectOutputs:
            self.graph.addHandler(self.updateEffectsFromGraph)

    def updateEffectsFromGraph(self):
        for effect in self.graph.subjects(RDF.type, L9['Effect']):
            settings = []
            for setting in self.graph.objects(effect, L9['setting']):
                d = self.graph.value(setting, L9['device'])
                a = self.graph.value(setting, L9['deviceAttr'])
                v = self.graph.value(setting, L9['value'])
                sv = self.graph.value(setting, L9['scaledValue'])
                if not (bool(v) ^ bool(sv)):
                    raise NotImplementedError

                settings.append((d, a, v if v is not None else sv, bool(sv)))

            if settings:
                self.effectOutputs[effect] = settings
            # also have to read eff :effectAttr [ :tint x; :tintStrength y ]
        
    def outputFromEffect(self, effectSettings, songTime):
        """
        From effect attr settings, like strength=0.75, to output device
        settings like light1/bright=0.72;light2/bright=0.78. This runs
        the effect code.
        """
        # both callers need to apply note overrides
        effectSettings = dict(effectSettings) # we should make everything into nice float and Color objects too

        strength = float(effectSettings[L9['strength']])
        if strength <= 0:
            return []

        out = {} # (dev, attr): value

        out.update(self.simpleOutput(strength,
                                     effectSettings.get(L9['colorScale'], None)))

        if self.effect.startswith(L9['effect/']):
            tail = 'effect_' + self.effect[len(L9['effect/']):]
            try:
                func = globals()[tail]
            except KeyError:
                pass
            else:
                out.update(func(effectSettings, strength, songTime))

        # todo: callers should prefer the dict form too
        outList = [(d, a, v) for (d, a), v in out.iteritems()]
        outList.sort()
        #import pprint; pprint.pprint(outList, width=170)
        return outList
                            
    def simpleOutput(self, strength, colorScale):
        out = {}
        for dev, devAttr, value, isScaled in self.effectOutputs.get(self.effect, []):
            if isScaled:
                value = scale(value, strength)
            if colorScale is not None and devAttr == L9['color']:
                value = scale(value, colorScale)
            out[(dev, devAttr)] = value
        return out
        


    

def effect_Curtain(effectSettings, strength, songTime):
    return {
        (L9['device/lowPattern%s' % n], L9['color']):
        literalColor(strength, strength, strength)
        for n in range(301,308+1)
        }
    
def effect_animRainbow(effectSettings, strength, songTime):
    out = {}
    tint = effectSettings.get(L9['tint'], '#ffffff')
    tintStrength = float(effectSettings.get(L9['tintStrength'], 0))
    print tint, tintStrength
    tr, tg, tb = hex_to_rgb(tint)
    for n in range(1, 5+1):
        scl = strength * nsin(songTime + n * .3)**3
        col = literalColor(
            scl * lerp(nsin(songTime + n * .2), tr/255, tintStrength),
            scl * lerp(nsin(songTime + n * .2 + .3), tg/255, tintStrength),
            scl * lerp(nsin(songTime + n * .3 + .6), tb/255, tintStrength))

        dev = L9['device/aura%s' % n]
        out.update({
            (dev, L9['color']): col,
            (dev, L9['zoom']): .9,
            })
        ang = songTime * 4
        out.update({
        (dev, L9['rx']): lerp(.27, .7, (n-1)/4) + .2 * math.sin(ang+n),
        (dev, L9['ry']): lerp(.46, .52, (n-1)/4) + .5 * math.cos(ang+n),
            })
    return out

def effect_pulseRainbow(effectSettings, strength, songTime):
    out = {}
    tint = effectSettings.get(L9['tint'], '#ffffff')
    tintStrength = float(effectSettings.get(L9['tintStrength'], 0))
    print tint, tintStrength
    tr, tg, tb = hex_to_rgb(tint)
    for n in range(1, 5+1):
        scl = strength 
        col = literalColor(
            scl * lerp(nsin(songTime + n * .2), tr/255, tintStrength),
            scl * lerp(nsin(songTime + n * .2 + .3), tg/255, tintStrength),
            scl * lerp(nsin(songTime + n * .3 + .6), tb/255, tintStrength))

        dev = L9['device/aura%s' % n]
        out.update({
            (dev, L9['color']): col,
            (dev, L9['zoom']): .5,
            })
        out.update({
        (dev, L9['rx']): lerp(.27, .7, (n-1)/4),
        (dev, L9['ry']): lerp(.46, .52, (n-1)/4),
            })
    return out

def effect_orangeSearch(effectSettings, strength, songTime):
    dev = L9['device/auraStage']
    return {(dev, L9['color']): '#c1905d',
            (dev, L9['rx']): lerp(.31, .68, nsquare(songTime / 2.0)),
            (dev, L9['ry']): lerp(.32, .4,  nsin(songTime / 5)),
            (dev, L9['zoom']): .88,
            }
    
def effect_Strobe(effectSettings, strength, songTime):
    rate = 2
    duty = .3
    offset = 0
    f = (((songTime + offset) * rate) % 1.0)
    c = (f < duty) * strength
    col = rgb_to_hex([c * 255, c * 255, c * 255])
    return {(L9['device/colorStrip'], L9['color']): Literal(col)}

def effect_lightning(effectSettings, strength, songTime):
    devs = [L9['device/veryLow1'], L9['device/veryLow2'],
            L9['device/veryLow3'], L9['device/veryLow4'],
            L9['device/veryLow5'], L9['device/backlight1'],
            L9['device/backlight2'], L9['device/backlight3'],
            L9['device/backlight4'], L9['device/backlight5'],
            L9['device/down2'], L9['device/down3'],
            L9['device/down4'], L9['device/hexLow3'],
            L9['device/hexLow5'], L9['device/lip1 5'],
            L9['device/postL1'], L9['device/postR1']]
    out = {}
    col = rgb_to_hex([255 * strength] * 3)
    for i, dev in enumerate(devs):
        n = noise((songTime * 8 + i * 6.543) % 100.0)
        if n > .4:
            out[(dev, L9['color'])] = col
    return out
