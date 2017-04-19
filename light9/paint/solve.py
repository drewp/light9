from __future__ import division
from light9.namespaces import RDF, L9
from PIL import Image
import decimal
import numpy
import scipy.misc
import cairo

class Solver(object):
    def __init__(self, graph):
        self.graph = graph
        self.samples = {} # uri: Image array
        
    def loadSamples(self):
        """learn what lights do from images"""

        with self.graph.currentState() as g:
            for samp in g.subjects(RDF.type, L9['LightSample']):
                path = 'show/dance2017/cam/test/%s' % g.value(samp, L9['path'])
                img = Image.open(path)
                img.thumbnail((100, 100))
                self.samples[samp] = scipy.misc.fromimage(img, mode='RGB').transpose((1, 0, 2))

    def draw(self, painting, w, h):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()
        
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(20)
        for stroke in painting['strokes']:
            for pt in stroke['pts']:
                op = ctx.move_to if pt is stroke['pts'][0] else ctx.line_to
                op(pt[0] / 4.0, pt[1] / 4.0) # todo scale

            r,g,b = [int(stroke['color'][i:i+2], 16) / 255.0
                     for i in 1, 3, 5]
            ctx.set_source_rgba(r, g, b, 1)
            ctx.stroke()
        # then blur?
        
        #surface.write_to_png('/tmp/surf.png')
        a = numpy.frombuffer(surface.get_data(), numpy.uint8)
        a.shape = (w, h, 4)
        return a[:w,:h,:3]
        
    def solve(self, painting):
        """
        given strokes of colors on a photo of the stage, figure out the
        best light settings to match the image
        """
        pic0 = self.draw(painting, 100, 48)
        sampleDist = {}
        for sample, picSample in sorted(self.samples.items()):
            dist = numpy.sum(numpy.power(pic0.astype(numpy.float)
                                         - picSample, 2), axis=None)**.5
            sampleDist[sample] = dist
        results = [(d, uri) for uri, d in sampleDist.items()]
        results.sort()
        import sys
        print >>sys.stderr, results, results[0][0] / results[1][0]
        sample = results[0][1]
        
        out = []
        def getVal(obj):
            lit = g.value(obj, L9['value']) or g.value(obj, L9['scaledValue'])
            ret = lit.toPython()
            if isinstance(ret, decimal.Decimal):
                ret = float(ret)
            return ret
        with self.graph.currentState() as g:
            for obj in g.objects(sample, L9['setting']):
                out.append((g.value(obj, L9['device']),
                            g.value(obj, L9['deviceAttr']),
                            getVal(obj)))
                           
        return out


    def simulationLayers(self, settings):
        """
        how should a simulation preview approximate the light settings
        (device attribute values) by combining photos we have?
        """
    
