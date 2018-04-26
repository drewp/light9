"""
some clients will support the concept of a named session that keeps
multiple instances of that client separate
"""
from rdflib import URIRef
from urllib import quote
from light9 import showconfig

def add_option(parser):
    parser.add_option(
        '-s', '--session',
        help="name of session used for levels and window position",
        default='default')

def getUri(appName, opts):
    return URIRef("%s/sessions/%s/%s" % (showconfig.showUri(), appName,
                                         quote(opts.session, safe='')))
