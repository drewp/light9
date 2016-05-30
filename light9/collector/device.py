from __future__ import division
import logging
import math
from light9.namespaces import L9, RDF, DEV
from webcolors import hex_to_rgb

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

def _8bit(f):
    return min(255, max(0, int(f * 255)))

def resolve(deviceType, deviceAttr, values):
    """
    return one value to use for this attr, given a set of them that
    have come in simultaneously
    """
    raise NotImplementedError
    
def toOutputAttrs(deviceType, deviceAttrSettings):
    """
    Given settings like {L9['color']: Literal('#ff0000')}, return a
    similar dict where the keys are output attrs and the values are
    suitable for Collector.setAttr
    """
    if deviceType == L9['ChauvetColorStrip']:
        color = deviceAttrSettings.get(L9['color'], '#000000')
        r, g, b = hex_to_rgb(color)
        return {
            L9['mode']: 215,
            L9['red']: r,
            L9['green']: g,
            L9['blue']: b
            }
    elif deviceType == L9['Dimmer']:
        return {L9['brightness']: _8bit(deviceAttrSettings.get(L9['brightness'], 0))}
    elif deviceType == L9['Mini15']:
        inp = deviceAttrSettings
        rx8 = float(inp.get(L9['rx'], 0)) / 540 * 255
        ry8 = float(inp.get(L9['ry'], 0)) / 240 * 255
        r, g, b = hex_to_rgb(inp.get(L9['color'], '#000000'))

        return {
            L9['xRotation']: int(math.floor(rx8)),
            # didn't find docs on this, but from tests it looks like 64 fine steps takes you to the next coarse step
            L9['xFine']: _8bit(1 - (rx8 % 1.0)),
            L9['yRotation']: int(math.floor(ry8)),
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
