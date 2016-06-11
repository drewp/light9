from rdflib import Namespace, RDF, RDFS


# Namespace was showing up in profiles
class FastNs(object):
    def __init__(self, base):
        self.ns = Namespace(base)
        self.cache = {}
    def __getitem__(self, term):
        if term not in self.cache:
            self.cache[term] = self.ns[term]
        return self.cache[term]
    __getattr__ = __getitem__

L9 = FastNs("http://light9.bigasterisk.com/")
MUS = Namespace("http://light9.bigasterisk.com/music/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
DCTERMS = Namespace("http://purl.org/dc/terms/")
DEV = Namespace("http://light9.bigasterisk.com/device/")
