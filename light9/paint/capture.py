import os
from rdflib import URIRef
from light9 import showconfig
from light9.rdfdb.patch import Patch
from light9.namespaces import L9
from light9.paint.solve import loadNumPy

def writeCaptureDescription(graph, ctx, uri, dev, relOutPath, settingsSubgraphCache, settings):
    graph.patch(Patch(addQuads=settings.statements(
        uri, ctx=ctx,
        settingRoot=URIRef('/'.join([showconfig.showUri(), 'capture', dev.rsplit('/')[1]])),
        settingsSubgraphCache=settingsSubgraphCache)))
    graph.patch(Patch(addQuads=[
        (dev, L9['capture'], uri, ctx),
        (uri, L9['imagePath'], URIRef('/'.join([showconfig.showUri(), relOutPath])), ctx),
        ]))
    
class CaptureLoader(object):
    def __init__(self, graph):
        self.graph = graph
        
    def loadImage(self, pic, thumb=(100, 100)):
        ip = self.graph.value(pic, L9['imagePath'])
        if not ip.startswith(showconfig.show()):
            raise ValueError(repr(ip))
        diskPath = os.path.join(showconfig.root(), ip[len(self.show):])
        return loadNumPy(diskPath, thumb)
        
    def devices(self):
        """devices for which we have any captured data"""

    def capturedSettings(self, device):
        """list of (pic, settings) we know for this device"""
        
