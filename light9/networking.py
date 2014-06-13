from urlparse import urlparse
from urllib import splitport
from showconfig import getGraph, showUri
from namespaces import L9

class ServiceAddress(object):
    def __init__(self, service):
        self.service = service

    def _url(self):
        graph = getGraph()
        net = graph.value(showUri(), L9['networking'])
        ret = graph.value(net, self.service)
        if ret is None:
            raise ValueError("no url for %s %s" % (showUri(), L9['networking']))
        return str(ret)

    @property
    def port(self):
        _, netloc, _, _, _, _ = urlparse(self._url())
        host, port = splitport(netloc)
        return int(port)

    @property
    def host(self):
        _, netloc, _, _, _, _ = urlparse(self._url())
        host, port = splitport(netloc)
        return host

    @property
    def url(self):
        return self._url()

    def path(self, more):
        return self.url + str(more)

dmxServer = ServiceAddress(L9['dmxServer'])
oscDmxServer = ServiceAddress(L9['oscDmxServer'])
musicPlayer = ServiceAddress(L9['musicPlayer'])
keyboardComposer = ServiceAddress(L9['keyboardComposer'])
curveCalc = ServiceAddress(L9['curveCalc'])
vidref = ServiceAddress(L9['vidref'])
effectEval = ServiceAddress(L9['effectEval'])
picamserve = ServiceAddress(L9['picamserve'])
rdfdb = ServiceAddress(L9['rdfdb'])
