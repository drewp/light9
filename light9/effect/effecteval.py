from __future__ import division
from rdflib import URIRef, Literal
from light9.namespaces import L9, RDF
from webcolors import rgb_to_hex, hex_to_rgb
from decimal import Decimal
import math

def literalColor(rnorm, gnorm, bnorm):
    return Literal(rgb_to_hex([rnorm * 255, gnorm * 255, bnorm * 255]))

def scale(value, strength):
    if isinstance(value, Literal):
        value = value.toPython()

    if isinstance(value, Decimal):
        value = float(value)
        
    if isinstance(value, basestring):
        if value[0] == '#':
            r,g,b = hex_to_rgb(value)
            return rgb_to_hex([r * strength, g * strength, b * strength])
    elif isinstance(value, (int, float)):
        return value * strength
    else:
        raise NotImplementedError(repr(value))
    
class EffectEval(object):
    """
    runs one effect's code to turn effect attr settings into output
    device settings. No state; suitable for reload().
    """
    def __init__(self, graph, effect):
        self.graph = graph
        self.effect = effect 

        # effect : [(dev, attr, value, isScaled)]
        self.effectOutputs = {}
        
        #for ds in g.objects(g.value(uri, L9['effectClass']), L9['deviceSetting']):
        #    self.setting = (g.value(ds, L9['device']), g.value(ds, L9['attr']))

        self.graph.addHandler(self.updateEffectsFromGraph)

    def updateEffectsFromGraph(self):
        self.effectOutputs = {}
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
        
    def outputFromEffect(self, effectSettings, songTime):
        """
        From effect attr settings, like strength=0.75, to output device
        settings like light1/bright=0.72;light2/bright=0.78. This runs
        the effect code.
        """
        attr, strength = effectSettings[0]
        strength = float(strength)
        assert attr == L9['strength']

        out = []
        for dev, attr, value, isScaled in self.effectOutputs.get(self.effect, []):
            if isScaled:
                value = scale(value, strength)
            out.append((dev, attr, value))
            
        if self.effect == L9['effect/RedStripzzz']: # throwaway
            mov = URIRef('http://light9.bigasterisk.com/device/moving1')
            col = [
                    ((songTime + .0) % 1.0),
                    ((songTime + .4) % 1.0),
                    ((songTime + .8) % 1.0),
                ]
            out.extend([
                # device, attr, lev
                
                (mov, L9['color'], Literal(rgb_to_hex([strength*x*255 for x in col]))),
                (mov, L9['rx'], Literal(100 + 70 * math.sin(songTime*2))),
            ] * (strength>0))
        elif self.effect == L9['effect/Curtain']:
            out.extend([
                (L9['device/lowPattern%s' % n], L9['color'], literalColor(0*strength, strength, strength)) for n in range(301,308+1)
                ])
        elif self.effect == L9['effect/animRainbow']:
            for n in range(1, 5+1):
                col = literalColor(
                        strength * (.5 + .5 * math.sin(songTime*6+n)),
                        strength * (.5 + .5 * math.sin(songTime*6+2+n)),
                        strength * (.5 + .5 * math.sin(songTime*6+4+n)))
                out.append((L9['device/aura%s' % n], L9['color'], col))
                
                    
        elif self.effect == L9['effect/Strobe']:
            attr, value = effectSettings[0]
            assert attr == L9['strength']
            strength = float(value)
            rate = 2
            duty = .3
            offset = 0
            f = (((songTime + offset) * rate) % 1.0)
            c = (f < duty) * strength
            col = rgb_to_hex([c * 255, c * 255, c * 255])
            out.extend([
                (L9['device/colorStrip'], L9['color'], Literal(col)),
            ])

        return out
        


    
