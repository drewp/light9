from __future__ import division
from rdflib import Literal
from decimal import Decimal
from webcolors import rgb_to_hex, hex_to_rgb


def scale(value, strength):
    if isinstance(value, Literal):
        value = value.toPython()

    if isinstance(value, Decimal):
        value = float(value)
        
    if isinstance(value, basestring):
        if value[0] == '#':
            if strength == '#ffffff':
                return value
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

    raise NotImplementedError("%r,%r" % (value, strength))
    
