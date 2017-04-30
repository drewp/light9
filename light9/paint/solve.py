from __future__ import division
from light9.namespaces import RDF, L9
from PIL import Image
import decimal
import numpy
import scipy.misc, scipy.ndimage
import cairo

# numpy images in this file are (x, y, c) layout.

def numpyFromCairo(surface):
    w, h = surface.get_width(), surface.get_height()
    a = numpy.frombuffer(surface.get_data(), numpy.uint8)
    a.shape = h, w, 4
    a = a.transpose((1, 0, 2))
    return a[:w,:h,:3]

def numpyFromPil(img):
    return scipy.misc.fromimage(img, mode='RGB').transpose((1, 0, 2))

def saveNumpy(path, img):
    scipy.misc.imsave(path, img.transpose((1, 0, 2)))

def parseHex(h):
    if h[0] != '#': raise ValueError(h)
    return [int(h[i:i+2], 16) for i in 1, 3, 5]

def scaledHex(h, scale):
    rgb = parseHex(h)
    rgb8 = (rgb * scale).astype(numpy.uint8)
    return '#%02x%02x%02x' % tuple(rgb8)
    
def colorRatio(col1, col2):
    rgb1 = parseHex(col1)
    rgb2 = parseHex(col2)
    return tuple([round(a / b, 3) for a, b in zip(rgb1, rgb2)])

def brightest(img):
    return numpy.amax(img, axis=(0, 1))

def getVal(graph, subj):
    lit = graph.value(subj, L9['value']) or graph.value(subj, L9['scaledValue'])
    ret = lit.toPython()
    if isinstance(ret, decimal.Decimal):
        ret = float(ret)
    return ret

def loadNumpy(path, thumb=(100, 100)):
    img = Image.open(path)
    img.thumbnail(thumb)
    return numpyFromPil(img)
    
class Solver(object):
    def __init__(self, graph):
        self.graph = graph
        self.samples = {} # uri: Image array
        self.fromPath = {} # basename: image array
        self.blurredSamples = {}
        self.sampleSettings = {} # (uri, path): { dev: { attr: val } }
        
    def loadSamples(self):
        """learn what lights do from images"""

        with self.graph.currentState() as g:
            for samp in g.subjects(RDF.type, L9['LightSample']):
                base = g.value(samp, L9['path']).toPython()
                path = 'show/dance2017/cam/test/%s' % base
                self.samples[samp] = self.fromPath[base] = loadNumpy(path)
                self.blurredSamples[samp] = self._blur(self.samples[samp])

                for s in g.objects(samp, L9['setting']):
                    d = g.value(s, L9['device'])
                    da = g.value(s, L9['deviceAttr'])
                    v = getVal(g, s)
                    key = (samp, g.value(samp, L9['path']).toPython())
                    self.sampleSettings.setdefault(key, {}).setdefault(d, {})[da] = v

    def _blur(self, img):
        return scipy.ndimage.gaussian_filter(img, 10, 0, mode='nearest')
                
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
                op(pt[0] / 4, pt[1] / 4) # todo scale

            r,g,b = parseHex(stroke['color'])
            ctx.set_source_rgb(r / 255, g / 255, b / 255)
            ctx.stroke()
        
        #surface.write_to_png('/tmp/surf.png')
        return numpyFromCairo(surface)
        
    def solve(self, painting):
        """
        given strokes of colors on a photo of the stage, figure out the
        best light settings to match the image
        """
        pic0 = self.draw(painting, 100, 48).astype(numpy.float)
        pic0Blur = self._blur(pic0)
        saveNumpy('/tmp/sample_paint_%s.png' % len(painting['strokes']),
                  pic0Blur)
        sampleDist = {}
        for sample, picSample in sorted(self.blurredSamples.items()):
            #saveNumpy('/tmp/sample_%s.png' % sample.split('/')[-1],
            #          f(picSample))
            dist = numpy.sum(numpy.absolute(pic0Blur - picSample), axis=None)
            sampleDist[sample] = dist
        results = [(d, uri) for uri, d in sampleDist.items()]
        results.sort()

        sample = results[0][1]

        # this is wrong; some wrong-alignments ought to be dimmer than full
        brightest0 = brightest(pic0)
        brightestSample = brightest(self.samples[sample])
        
        if max(brightest0) < 1 / 255:
            return []

        scale = brightest0 / brightestSample
        
        out = []
        with self.graph.currentState() as g:
            for obj in g.objects(sample, L9['setting']):
                attr = g.value(obj, L9['deviceAttr'])
                val = getVal(g, obj)
                if attr == L9['color']:
                    val = scaledHex(val, scale)
                out.append((g.value(obj, L9['device']), attr, val))
                           
        return out

    def combineImages(self, layers):
        """make a result image from our self.samples images"""
        out = (self.fromPath.itervalues().next() * 0).astype(numpy.uint16)
        for layer in layers:
            colorScaled = self.fromPath[layer['path']] * layer['color']
            out += colorScaled.astype(numpy.uint16)
        numpy.clip(out, 0, 255, out)
        return out.astype(numpy.uint8)
        
    def simulationLayers(self, settings):
        """
        how should a simulation preview approximate the light settings
        (device attribute values) by combining photos we have?
        """

        compiled = {} # dev: { attr: val }
        for row in settings:
            compiled.setdefault(row[0], {})[row[1]] = row[2]
        
        layers = []

        for (sample, path), s in self.sampleSettings.items():
            for d, dav in s.items():
                if d not in compiled:
                    continue
                requestedAttrs = compiled[d].copy()
                picAttrs = dav.copy()
                del requestedAttrs[L9['color']]
                del picAttrs[L9['color']]
                if requestedAttrs == picAttrs:
                    requestedColor = compiled[d][L9['color']]
                    picColor = dav[L9['color']]
                    layers.append({'path': path,
                                   'color': colorRatio(requestedColor,
                                                       picColor)})
        
        return layers
