import os
from rdflib import URIRef
from light9 import showconfig
from rdfdb.patch import Patch
from light9.namespaces import L9, RDF
from light9.paint.solve import loadNumpy


def writeCaptureDescription(graph, ctx, session, uri, dev, outPath,
                            settingsSubgraphCache, settings):
    graph.patch(
        Patch(addQuads=settings.statements(
            uri,
            ctx=ctx,
            settingRoot=URIRef('/'.join(
                [showconfig.showUri(), 'capture',
                 dev.rsplit('/')[1]])),
            settingsSubgraphCache=settingsSubgraphCache)))
    graph.patch(
        Patch(addQuads=[
            (dev, L9['capture'], uri, ctx),
            (session, L9['capture'], uri, ctx),
            (uri, RDF.type, L9['LightSample'], ctx),
            (uri, L9['imagePath'],
             URIRef('/'.join([showconfig.showUri(), outPath])), ctx),
        ]))
    graph.suggestPrefixes(
        ctx, {
            'cap': uri.rsplit('/', 1)[0] + '/',
            'showcap': showconfig.showUri() + '/capture/'
        })


class CaptureLoader(object):

    def __init__(self, graph):
        self.graph = graph

    def loadImage(self, pic, thumb=(100, 100)):
        ip = self.graph.value(pic, L9['imagePath'])
        if not ip.startswith(showconfig.show()):
            raise ValueError(repr(ip))
        diskPath = os.path.join(showconfig.root(), ip[len(self.show):])
        return loadNumpy(diskPath, thumb)

    def devices(self):
        """devices for which we have any captured data"""

    def capturedSettings(self, device):
        """list of (pic, settings) we know for this device"""
