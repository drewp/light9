from __future__ import division
import logging
import math
from light9.namespaces import L9, RDF, DEV
from rdflib import Literal
from webcolors import hex_to_rgb, rgb_to_hex

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
    if not isinstance(f, float):
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
        
    if deviceType == L9['ChauvetColorStrip']:
        color = deviceAttrSettings.get(L9['color'], '#000000')
        r, g, b = hex_to_rgb(color)
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
    else:
        raise NotImplementedError('device %r' % deviceType)
