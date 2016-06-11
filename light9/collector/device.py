from __future__ import division
import logging
import math
from light9.namespaces import L9, RDF, DEV
from rdflib import Literal
from webcolors import hex_to_rgb, rgb_to_hex
from colormath.color_objects import sRGBColor, CMYColor
import colormath.color_conversions

log = logging.getLogger('device')

class Device(object):
    def setAttrs():
        pass


class ChauvetColorStrip(Device):
    """
     device attrs:
       color
    """
        
class Mini15(Device):
    """
    plan:

      device attrs
        rx, ry
        color
        gobo
        goboShake
        imageAim (configured with a file of calibration data)
    """
def clamp255(x):
    return min(255, max(0, x))
    
def _8bit(f):
    if not isinstance(f, (int, float)):
        raise TypeError(repr(f))
    return clamp255(int(f * 255))

def resolve(deviceType, deviceAttr, values):
    """
    return one value to use for this attr, given a set of them that
    have come in simultaneously. len(values) >= 1.
    """
    if len(values) == 1:
        return values[0]
    if deviceAttr == L9['color']:
        rgbs = [hex_to_rgb(v) for v in values]
        return rgb_to_hex([max(*component) for component in zip(*rgbs)])
    # angles should perhaps use average; gobo choice use the most-open one
    return max(values)
    
def toOutputAttrs(deviceType, deviceAttrSettings):
    """
    Given device attr settings like {L9['color']: Literal('#ff0000')},
    return a similar dict where the keys are output attrs (like
    L9['red']) and the values are suitable for Collector.setAttr
    """
    def floatAttr(attr, default=0):
        out = deviceAttrSettings.get(attr)
        if out is None:
            return default
        return float(out.toPython())

    def rgbAttr(attr):
        color = deviceAttrSettings.get(attr, '#000000')
        r, g, b = hex_to_rgb(color)
        return r, g, b

    def cmyAttr(attr):
        rgb = sRGBColor.new_from_rgb_hex(deviceAttrSettings.get(attr, '#000000'))
        out = colormath.color_conversions.convert_color(rgb, CMYColor)
        return (
            _8bit(out.cmy_c),
            _8bit(out.cmy_m),
            _8bit(out.cmy_y))

    def fine16Attr(attr):
        x = floatAttr(attr)
        hi = _8bit(x)
        lo = _8bit((x * 255) % 1.0)
        return hi, lo
        
    if deviceType == L9['ChauvetColorStrip']:
        r, g, b = rgbAttr(L9['color'])
        return {
            L9['mode']: 215,
            L9['red']: r,
            L9['green']: g,
            L9['blue']: b
            }
    elif deviceType == L9['SimpleDimmer']:
        return {L9['level']: _8bit(floatAttr(L9['brightness']))}
    elif deviceType == L9['Mini15']:
        inp = deviceAttrSettings
        rx8 = float(inp.get(L9['rx'], 0)) / 540 * 255
        ry8 = float(inp.get(L9['ry'], 0)) / 240 * 255
        r, g, b = hex_to_rgb(inp.get(L9['color'], '#000000'))

        return {
            L9['xRotation']: clamp255(int(math.floor(rx8))),
            # didn't find docs on this, but from tests it looks like 64 fine steps takes you to the next coarse step
            L9['xFine']: _8bit(1 - (rx8 % 1.0)),
            L9['yRotation']: clamp255(int(math.floor(ry8))),
            L9['yFine']: _8bit((ry8 % 1.0) / 4),
            L9['rotationSpeed']: 0,
            L9['dimmer']: 255,
            L9['red']: r,
            L9['green']: g,
            L9['blue']: b,
            L9['colorChange']: 0,
            L9['colorSpeed']: 0,
            L9['goboShake']: 0,
            L9['goboChoose']: 0,
        }
    elif deviceType == L9['ChauvetHex12']:
        out = {}
        out[L9['red']], out[L9['green']], out[L9['blue']] = r, g, b = rgbAttr(L9['color'])
        out[L9['amber']] = 0
        out[L9['white']] = min(r, g, b)
        out[L9['uv']] = _8bit(floatAttr(L9['uv']))
        return out
    elif deviceType == L9['Source4LedSeries2']:
        out = {}
        out[L9['red']], out[L9['green']], out[L9['blue']] = rgbAttr(L9['color'])
        out[L9['strobe']] = 0
        out[L9['fixed255']] = 255
        for num in range(7):
            out[L9['fixed128_%s' % num]] = 128
        return out        
    elif deviceType == L9['MacAura']:
        out = {
            L9['shutter']: 22,
            L9['dimmer']: 255,
            L9['zoom']: _8bit(floatAttr(L9['zoom'])),
            L9['fixtureControl']: 0,
            L9['colorWheel']: 0,
            L9['colorTemperature']: 128,
            L9['fx1Select']: 0,
            L9['fx1Adjust']: 0,
            L9['fx2Select']: 0,
            L9['fx2Adjust']: 0,
            L9['fxSync']: 0,
            L9['auraShutter']: 22,
            L9['auraDimmer']: 0,
            L9['auraColorWheel']: 0,
            L9['auraRed']: 0,
            L9['auraGreen']: 0,
            L9['auraBlue']: 0,
        }
        out[L9['pan']], out[L9['panFine']] = fine16Attr(L9['rx'])
        out[L9['tilt']], out[L9['tiltFine']] = fine16Attr(L9['ry'])
        out[L9['red']], out[L9['green']], out[L9['blue']] = rgbAttr(L9['color'])
        out[L9['white']] = 0

        return out
    elif deviceType == L9['MacQuantum']:
        out = {
            L9['dimmerFadeLo']: 0,
            L9['shutter']: 30, # strobe is in here too: slow @ 50 -> fast @ 200
            L9['fixtureControl']: 0,
            L9['fx1Select']:  0,
            L9['fx1Adjust']:  0,
            L9['fx2Select']:  0,
            L9['fx2Adjust']:  0,
            L9['fxSync']:  0,            
            }

        # note these values are set to 'fade', so they update slowly. Haven't found where to turn that off.
        out[L9['cyan']], out[L9['magenta']], out[L9['yellow']] = cmyAttr(L9['color'])
        
        out[L9['focusHi']], out[L9['focusLo']] = fine16Attr(L9['focus'])
        out[L9['panHi']], out[L9['panLo']] = fine16Attr(L9['rx'])
        out[L9['tiltHi']], out[L9['tiltLo']] = fine16Attr(L9['ry'])
        out[L9['zoomHi']], out[L9['zoomLo']] = fine16Attr(L9['zoom'])
        out[L9['dimmerFadeHi']] = 0 if deviceAttrSettings.get(L9['color'], '#000000') == '#000000' else 255

        out[L9['goboChoice']] = {
            L9['open']: 0,
            L9['spider']: 36,
            L9['windmill']: 41,
            L9['limbo']: 46,
            L9['brush']: 51,
            L9['whirlpool']: 56,
            L9['stars']: 61,
            }[deviceAttrSettings.get(L9['gobo'], L9['open'])]

        # my goboSpeed deviceAttr goes 0=stopped to 1=fastest (using one direction only)
        x = .5 + .5 * floatAttr(L9['goboSpeed'])
        out[L9['goboSpeedHi']] = _8bit(x)
        out[L9['goboSpeedLo']] = _8bit((x * 255) % 1.0)
        
        out.update( {
            L9['colorWheel']: 0,
            L9['goboStaticRotate']: 0,
            L9['prismRotation']: _8bit(floatAttr(L9['prism'])),
            L9['iris']: _8bit(floatAttr(L9['iris']) * (200/255)),
            })
        return out
    else:
        raise NotImplementedError('device %r' % deviceType)
