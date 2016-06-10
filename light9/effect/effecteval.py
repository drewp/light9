from __future__ import division
from rdflib import URIRef, Literal
from light9.namespaces import L9, RDF
from webcolors import rgb_to_hex
import math


class EffectEval(object):
    """
    runs one effect's code to turn effect attr settings into output
    device settings. No state; suitable for reload().
    """
    def __init__(self, graph, effect):
        self.graph = graph
        self.effect = effect
        
        #for ds in g.objects(g.value(uri, L9['effectClass']), L9['deviceSetting']):
        #    self.setting = (g.value(ds, L9['device']), g.value(ds, L9['attr']))

    def outputFromEffect(self, effectSettings, songTime):
        """
        From effect attr settings, like strength=0.75, to output device
        settings like light1/bright=0.72;light2/bright=0.78. This runs
        the effect code.
        """
        attr, value = effectSettings[0]
        value = float(value)
        assert attr == L9['strength']
        c = int(255 * value)
        color = [0, 0, 0]
        if self.effect == L9['effect/RedStrip']: # throwaway

            mov = URIRef('http://light9.bigasterisk.com/device/moving1')
            col = [
                    (songTime + .0) % 1.0,
                    (songTime + .4) % 1.0,
                    (songTime + .8) % 1.0,
                ]
            return [
                # device, attr, lev
                
                (mov, L9['color'], Literal(rgb_to_hex([value*x*255 for x in col]))),
                (mov, L9['rx'], Literal(100 + 70 * math.sin(songTime*2))),
            ] * (value>0)

        elif self.effect == L9['effect/BlueStrip']:
            color[2] = c
        elif self.effect == L9['effect/WorkLight']:
            color[1] = c
        elif self.effect == L9['effect/Curtain']:
            color[0] = color[2] = 70/255 * c
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
            return [
                (L9['device/colorStrip'], L9['color'], Literal(col)),
            ]
        else:
            color[0] = color[1] = color[2] = c

        return [
            # device, attr, lev
            (URIRef('http://light9.bigasterisk.com/device/moving1'),
             URIRef("http://light9.bigasterisk.com/color"),
             Literal(rgb_to_hex(color)))
            ]
        


    
