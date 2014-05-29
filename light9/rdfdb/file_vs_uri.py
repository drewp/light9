"""
note that if there are ambiguities in dirUriMap, you'll get
undefined results that depend on python's items() order.
"""
import os
from rdflib import URIRef

def uriFromFile(dirUriMap, filename):
    assert filename.endswith('.n3'), filename
    for d, prefix in dirUriMap.items():
        if filename.startswith(d):
            return URIRef(prefix + filename[len(d):-len('.n3')])
    raise ValueError("filename %s doesn't start with any of %s" %
                     (filename, dirUriMap.keys()))

def fileForUri(dirUriMap, ctx):
    assert isinstance(ctx, URIRef), ctx
    for d, prefix in dirUriMap.items():
        if ctx.startswith(prefix):
            return d + ctx[len(prefix):] + '.n3'
    raise ValueError("don't know what filename to use for %s" % ctx)

def correctToTopdirPrefix(dirUriMap, inFile):
    if not any(inFile.startswith(prefix) for prefix in dirUriMap):
        for prefix in dirUriMap:
            prefixAbs = os.path.abspath(prefix)
            if inFile.startswith(prefixAbs):
                inFile = prefix + inFile[len(prefixAbs):]
                break
        else:
            raise ValueError("can't correct %s to start with one of %s" %
                             (inFile, dirUriMap.keys()))
    return inFile
