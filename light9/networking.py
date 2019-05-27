from rdflib import URIRef
from urllib.parse import urlparse
from .showconfig import getGraph, showUri
from .namespaces import L9


class ServiceAddress(object):

    def __init__(self, service):
        self.service = service

    def _url(self) -> URIRef:
        graph = getGraph()
        net = graph.value(showUri(), L9['networking'])
        ret = graph.value(net, self.service)
        if ret is None:
            raise ValueError("no url for %s -> %s -> %s" %
                             (showUri(), L9['networking'], self.service))
        assert isinstance(ret, URIRef)
        return ret

    @property
    def port(self):
        return urlparse(self._url()).port

    @property
    def host(self):
        return urlparse(self._url()).hostname

    @property
    def url(self) -> URIRef:
        return self._url()

    value = url

    def path(self, more):
        return self.url + str(more)


captureDevice = ServiceAddress(L9['captureDevice'])
curveCalc = ServiceAddress(L9['curveCalc'])
dmxServer = ServiceAddress(L9['dmxServer'])
dmxServerZmq = ServiceAddress(L9['dmxServerZmq'])
collector = ServiceAddress(L9['collector'])
collectorZmq = ServiceAddress(L9['collectorZmq'])
effectEval = ServiceAddress(L9['effectEval'])
effectSequencer = ServiceAddress(L9['effectSequencer'])
keyboardComposer = ServiceAddress(L9['keyboardComposer'])
musicPlayer = ServiceAddress(L9['musicPlayer'])
oscDmxServer = ServiceAddress(L9['oscDmxServer'])
paintServer = ServiceAddress(L9['paintServer'])
picamserve = ServiceAddress(L9['picamserve'])
rdfdb = ServiceAddress(L9['rdfdb'])
subComposer = ServiceAddress(L9['subComposer'])
subServer = ServiceAddress(L9['subServer'])
vidref = ServiceAddress(L9['vidref'])

patchReceiverUpdateHost = ServiceAddress(L9['patchReceiverUpdateHost'])
