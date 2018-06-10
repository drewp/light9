from __future__ import division
from rdflib import URIRef, Literal
from light9.namespaces import L9, RDF, DEV
from webcolors import rgb_to_hex, hex_to_rgb
from colorsys import hsv_to_rgb
from decimal import Decimal
import math
import traceback
from noise import pnoise1
import logging
import time
from light9.effect.settings import DeviceSettings
from light9.effect.scale import scale
import random
random.seed(0)
print "reload effecteval"

log = logging.getLogger('effecteval')

def literalColor(rnorm, gnorm, bnorm):
    return Literal(rgb_to_hex([int(rnorm * 255), int(gnorm * 255), int(bnorm * 255)]))

def literalColorHsv(h, s, v):
    return literalColor(*hsv_to_rgb(h, s, v))
    
def nsin(x): return (math.sin(x * (2 * math.pi)) + 1) / 2
def ncos(x): return (math.cos(x * (2 * math.pi)) + 1) / 2
def nsquare(t, on=.5):
    return (t % 1.0) < on
def lerp(a, b, t):
    return a + (b - a) * t
def noise(t):
    return pnoise1(t % 1000.0, 2)
def clamp(lo, hi, x):
    return max(lo, min(hi, x))
    
class EffectEval(object):
    """
    runs one effect's code to turn effect attr settings into output
    device settings. No state; suitable for reload().
    """
    def __init__(self, graph, effect, simpleOutputs):
        self.graph = graph
        self.effect = effect
        self.simpleOutputs = simpleOutputs

    def outputFromEffect(self, effectSettings, songTime, noteTime):
        """
        From effect attr settings, like strength=0.75, to output device
        settings like light1/bright=0.72;light2/bright=0.78. This runs
        the effect code.
        """
        # both callers need to apply note overrides
        effectSettings = dict(effectSettings) # we should make everything into nice float and Color objects too

        strength = float(effectSettings[L9['strength']])
        if strength <= 0:
            return DeviceSettings(self.graph, []), {'zero': True}

        report = {}
        out = {} # (dev, attr): value

        out.update(self.simpleOutputs.values(
            self.effect, strength, effectSettings.get(L9['colorScale'], None)))

        if self.effect.startswith(L9['effect/']):
            tail = 'effect_' + self.effect[len(L9['effect/']):]
            try:
                func = globals()[tail]
            except KeyError:
                report['error'] = 'effect code not found for %s' % self.effect
            else:
                out.update(func(effectSettings, strength, songTime, noteTime))

        outList = [(d, a, v) for (d, a), v in out.iteritems()]
        return DeviceSettings(self.graph, outList), report
                  

def effect_Curtain(effectSettings, strength, songTime, noteTime):
    return {
        (L9['device/lowPattern%s' % n], L9['color']):
        literalColor(strength, strength, strength)
        for n in range(301,308+1)
        }
    
def effect_animRainbow(effectSettings, strength, songTime, noteTime):
    out = {}
    tint = effectSettings.get(L9['tint'], '#ffffff')
    tintStrength = float(effectSettings.get(L9['tintStrength'], 0))
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

def effect_auraSparkles(effectSettings, strength, songTime, noteTime):
    out = {}
    tint = effectSettings.get(L9['tint'], '#ffffff')
    tintStrength = float(effectSettings.get(L9['tintStrength'], 0))
    print effectSettings
    tr, tg, tb = hex_to_rgb(tint)
    for n in range(1, 5+1):
        scl = strength * ((int(songTime * 10) % n) < 1)
        col = literalColorHsv((songTime + (n / 5)) % 1, 1, scl)

        dev = L9['device/aura%s' % n]
        out.update({
            (dev, L9['color']): col,
            (dev, L9['zoom']): .95,
            })
        ang = songTime * 4
        out.update({
        (dev, L9['rx']): lerp(.27, .8, (n-1)/4) + .2 * math.sin(ang+n),
        (dev, L9['ry']): lerp(.46, .52, (n-1)/4) + .4 * math.cos(ang+n),
            })
    return out

def effect_qpan(effectSettings, strength, songTime, noteTime):
    dev = L9['device/q2']
    dur = 4
    col = scale(scale('#ffffff', strength),
                effectSettings.get(L9['colorScale']) or '#ffffff')
    return {
        (dev, L9['color']): col,
        (dev, L9['focus']): 0.589,
        (dev, L9['rx']): lerp(0.778, 0.291, clamp(0, 1, noteTime / dur)),
        (dev, L9['ry']): 0.383,
        (dev, L9['zoom']): 0.714,
    }

def effect_pulseRainbow(effectSettings, strength, songTime, noteTime):
    out = {}
    tint = effectSettings.get(L9['tint'], '#ffffff')
    tintStrength = float(effectSettings.get(L9['tintStrength'], 0))
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


def effect_aurawash(effectSettings, strength, songTime, noteTime):
    out = {}
    scl = strength
    period = float(effectSettings.get(L9['period'], 125/60/4))
    if period < .05:
        quantTime = songTime
    else:
        quantTime = int(songTime / period) * period
    noisePos = quantTime * 6.3456
    
    col = literalColorHsv(noise(noisePos), 1, scl)
    col = scale(col, effectSettings.get(L9['colorScale']) or '#ffffff')
                
    print songTime, quantTime, col

    for n in range(1, 5+1):
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

def effect_qsweep(effectSettings, strength, songTime, noteTime):
    out = {}
    period = float(effectSettings.get(L9['period'], 2))

    col = effectSettings.get(L9['colorScale'], '#ffffff')
    col = scale(col, effectSettings.get(L9['strength'], 1))

    
    for n in range(1, 3+1):
        dev = L9['device/q%s' % n]
        out.update({
            (dev, L9['color']): col,
            (dev, L9['zoom']): effectSettings.get(L9['zoom'], .5),
            })
        out.update({
            (dev, L9['rx']):
            lerp(.3, .8, nsin(songTime / period + n / 4)),
        (dev, L9['ry']): effectSettings.get(L9['ry'], .2),
            })
    return out

def effect_qsweepusa(effectSettings, strength, songTime, noteTime):
    out = {}
    period = float(effectSettings.get(L9['period'], 2))

    colmap = {
        1: '#ff0000',
        2: '#888888',
        3: '#5050ff',
    }
    
    for n in range(1, 3+1):
        dev = L9['device/q%s' % n]
        out.update({
            (dev, L9['color']): scale(colmap[n], effectSettings.get(L9['strength'], 1)),
            (dev, L9['zoom']): effectSettings.get(L9['zoom'], .5),
            })
        out.update({
            (dev, L9['rx']):
            lerp(.3, .8, nsin(songTime / period + n / 4)),
            (dev, L9['ry']): effectSettings.get(L9['ry'], .5),
            })
    return out

chase1_members = [
        DEV['backlight1'],
        DEV['lip1'],
        DEV['backlight2'],
        DEV['down2'],
        DEV['lip2'],
        DEV['backlight3'],
        DEV['down3'],
        DEV['lip3'],
        DEV['backlight4'],
        DEV['down4'],
        DEV['lip4'],
        DEV['backlight5'],
        DEV['down5Edge'],
        DEV['lip5'],
        #DEV['upCenter'],
        ]
chase2_members = chase1_members * 10
random.shuffle(chase2_members)

def effect_chase1(effectSettings, strength, songTime, noteTime):
    members = chase1_members + chase1_members[-2:0:-1]
    
    out = {}
    period = float(effectSettings.get(L9['period'], 2 / len(members)))

    for i, dev in enumerate(members):
        cursor = (songTime / period) % float(len(members))
        dist = abs(i - cursor)
        radius = 3
        if dist < radius:
            col = effectSettings.get(L9['colorScale'], '#ffffff')
            col = scale(col, effectSettings.get(L9['strength'], 1))
            col = scale(col, (1 - dist / radius))
        
            out.update({
                (dev, L9['color']): col,
            })
    return out

def effect_chase2(effectSettings, strength, songTime, noteTime):
    members = chase2_members
    
    out = {}
    period = float(effectSettings.get(L9['period'], 0.3))

    for i, dev in enumerate(members):
        cursor = (songTime / period) % float(len(members))
        dist = abs(i - cursor)
        radius = 3
        if dist < radius:
            col = effectSettings.get(L9['colorScale'], '#ffffff')
            col = scale(col, effectSettings.get(L9['strength'], 1))
            col = scale(col, (1 - dist / radius))
        
            out.update({
                (dev, L9['color']): col,
            })
    return out
    
def effect_whirlscolor(effectSettings, strength, songTime, noteTime):
    out = {}

    col = effectSettings.get(L9['colorScale'], '#ffffff')
    col = scale(col, effectSettings.get(L9['strength'], 1))
    
    for n in (1, 3):
        dev = L9['device/q%s' % n]
        scl = strength
        col = literalColorHsv(((songTime / 5) + (n / 5)) % 1, 1, scl)
        out.update({
            (dev, L9['color']): col,
            })

    return out


def effect_orangeSearch(effectSettings, strength, songTime, noteTime):
    dev = L9['device/auraStage']
    return {(dev, L9['color']): '#a885ff',
            (dev, L9['rx']): lerp(.65, 1, nsin(songTime / 2.0)),
            (dev, L9['ry']): .6,
            (dev, L9['zoom']): 1,
            }
    
def effect_Strobe(effectSettings, strength, songTime, noteTime):
    rate = 2
    duty = .3
    offset = 0
    f = (((songTime + offset) * rate) % 1.0)
    c = (f < duty) * strength
    col = rgb_to_hex([int(c * 255), int(c * 255), int(c * 255)])
    return {(L9['device/colorStrip'], L9['color']): Literal(col)}

def effect_lightning(effectSettings, strength, songTime, noteTime):
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
    col = rgb_to_hex([int(255 * strength)] * 3)
    for i, dev in enumerate(devs):
        n = noise(songTime * 8 + i * 6.543)
        if n > .4:
            out[(dev, L9['color'])] = col
    return out
