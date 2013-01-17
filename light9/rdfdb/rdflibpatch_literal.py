import sys
if sys.path[0] == '/usr/lib/python2.7/dist-packages':
    # nosetests puts this in
    sys.path = sys.path[1:]

from rdflib.term import _PLAIN_LITERAL_TYPES, _XSD_DOUBLE, _XSD_DECIMAL, Literal
from re import sub

def _literal_n3(self, use_plain=False, qname_callback=None):
    if use_plain and self.datatype in _PLAIN_LITERAL_TYPES:
        try:
            self.toPython() # check validity
            # this is a bit of a mess - 
            # in py >=2.6 the string.format function makes this easier
            # we try to produce "pretty" output
            if self.datatype == _XSD_DOUBLE:
                # this is the drewp fix
                return sub(r"\.?0*e","e", u'%e' % float(self))
            elif self.datatype == _XSD_DECIMAL:
                return sub("0*$","0",u'%f' % float(self))
            else:
                return u'%s' % self
        except ValueError:
            pass # if it's in, we let it out?

    encoded = self._quote_encode()

    datatype = self.datatype
    quoted_dt = None
    if datatype:
        if qname_callback:
            quoted_dt = qname_callback(datatype)
        if not quoted_dt:
            quoted_dt = "<%s>" % datatype

    language = self.language
    if language:
        if datatype:
            # TODO: this isn't valid RDF (it's datatype XOR language)
            return '%s@%s^^%s' % (encoded, language, quoted_dt)
        return '%s@%s' % (encoded, language)
    elif datatype:
        return '%s^^%s' % (encoded, quoted_dt)
    else:
        return '%s' % encoded

def patch():
    Literal._literal_n3 = _literal_n3

import unittest
class TestDoubleOutput(unittest.TestCase):
    def testNoDanglingPoint(self):
        vv = Literal("0.88", datatype=_XSD_DOUBLE)
        out = _literal_n3(vv, use_plain=True)
        print out
        self.assert_(out in ["8.8e-01", "0.88"], out)
