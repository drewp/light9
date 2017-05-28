from __future__ import division
from light9.namespaces import RDF, L9, DEV
from PIL import Image
import numpy
import scipy.misc, scipy.ndimage, scipy.optimize
import cairo
import logging

from light9.effect.settings import DeviceSettings, parseHex, toHex

log = logging.getLogger('solve')

# numpy images in this file are (x, y, c) layout.

def numpyFromCairo(surface):
    w, h = surface.get_width(), surface.get_height()
    a = numpy.frombuffer(surface.get_data(), numpy.uint8)
    a.shape = h, w, 4
    a = a.transpose((1, 0, 2))
    return a[:w,:h,:3]

def numpyFromPil(img):
    return scipy.misc.fromimage(img, mode='RGB').transpose((1, 0, 2))

def loadNumpy(path, thumb=(100, 100)):
    img = Image.open(path)
    img.thumbnail(thumb)
    return numpyFromPil(img)

def saveNumpy(path, img):
    # maybe this should only run if log level is debug?
    scipy.misc.imsave(path, img.transpose((1, 0, 2)))

def scaledHex(h, scale):
    rgb = parseHex(h)
    rgb8 = (rgb * scale).astype(numpy.uint8)
    return '#%02x%02x%02x' % tuple(rgb8)
    
def colorRatio(col1, col2):
    rgb1 = parseHex(col1)
    rgb2 = parseHex(col2)
    def div(x, y):
        if y == 0:
            return 0
        return round(x / y, 3)
    return tuple([div(a, b) for a, b in zip(rgb1, rgb2)])

def brightest(img):
    return numpy.amax(img, axis=(0, 1))


class Solver(object):
    def __init__(self, graph):
        self.graph = graph
        self.samples = {} # uri: Image array
        self.fromPath = {} # basename: image array
        self.blurredSamples = {}
        self.sampleSettings = {} # (uri, path): DeviceSettings
        
    def loadSamples(self):
        """learn what lights do from images"""

        with self.graph.currentState() as g:
            for samp in g.subjects(RDF.type, L9['LightSample']):
                base = g.value(samp, L9['path']).toPython()
                path = 'show/dance2017/cam/test/%s' % base
                self.samples[samp] = self.fromPath[base] = loadNumpy(path)
                self.blurredSamples[samp] = self._blur(self.samples[samp])
                
                key = (samp, g.value(samp, L9['path']).toPython().encode('utf8'))
                self.sampleSettings[key] = DeviceSettings.fromResource(self.graph, samp)

    def _blur(self, img):
        return scipy.ndimage.gaussian_filter(img, 10, 0, mode='nearest')

    def draw(self, painting):
        return self._draw(painting, 100, 48)
        
    def _draw(self, painting, w, h):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()
        
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(w / 5) # ?
        for stroke in painting['strokes']:
            for pt in stroke['pts']:
                op = ctx.move_to if pt is stroke['pts'][0] else ctx.line_to
                op(pt[0] * w, pt[1] * h)

            r,g,b = parseHex(stroke['color'])
            ctx.set_source_rgb(r / 255, g / 255, b / 255)
            ctx.stroke()
        
        surface.write_to_png('/tmp/surf.png')
        return numpyFromCairo(surface)


    def _imgDist(self, a, b):
        return numpy.sum(numpy.absolute(a - b), axis=None)
        
    def bestMatch(self, img):
        """the one sample that best matches this image"""
        results = []
        for uri, img2 in self.samples.iteritems():
            results.append((self._imgDist(img, img2), uri, img2))
        results.sort()
        log.info('results:')
        for d,u,i in results:
            log.info('%s %g', u, d)
        saveNumpy('/tmp/bestsamp.png', results[0][2])
        return results[0][1]
        
    def solve(self, painting):
        """
        given strokes of colors on a photo of the stage, figure out the
        best light DeviceSettings to match the image
        """
        pic0 = self.draw(painting).astype(numpy.float)
        pic0Blur = self._blur(pic0)
        saveNumpy('/tmp/sample_paint_%s.png' % len(painting['strokes']),
                  pic0Blur)
        sampleDist = {}
        for sample, picSample in sorted(self.blurredSamples.items()):
            #saveNumpy('/tmp/sample_%s.png' % sample.split('/')[-1],
            #          f(picSample))
            dist = self._imgDist(pic0Blur, picSample)
            sampleDist[sample] = dist
        results = [(d, uri) for uri, d in sampleDist.items()]
        results.sort()

        sample = results[0][1]

        # this is wrong; some wrong-alignments ought to be dimmer than full
        brightest0 = brightest(pic0)
        brightestSample = brightest(self.samples[sample])
        
        if max(brightest0) < 1 / 255:
            return DeviceSettings(self.graph, [])

        scale = brightest0 / brightestSample

        s = DeviceSettings.fromResource(self.graph, sample)
        # missing color scale, but it was wrong to operate on all devs at once
        return s

    def solveBrute(self, painting):
        pic0 = self.draw(painting).astype(numpy.float)

        colorSteps = 3
        colorStep = 1. / colorSteps

        dims = [
            (DEV['aura1'], L9['rx'], [slice(.2, .7+.1, .1)]),
            (DEV['aura1'], L9['ry'], [slice(.573, .573+1, 1)]),
            (DEV['aura1'], L9['color'], [slice(0, 1 + colorStep, colorStep),
                                         slice(0, 1 + colorStep, colorStep),
                                         slice(0, 1 + colorStep, colorStep)]),
        ]
        
        def drawError(x):
            settings = DeviceSettings.fromVector(self.graph, x)
            preview = self.combineImages(self.simulationLayers(settings))
            saveNumpy('/tmp/x_%s.png' % abs(hash(settings)), preview)
            
            diff = preview.astype(numpy.float) - pic0
            out = scipy.sum(abs(diff))
            
            #print 'measure at', x, 'drawError=', out
            return out
            
        x0, fval, grid, Jout = scipy.optimize.brute(
            drawError,
            sum([s for dev, da, s in dims], []),
            finish=None,
            disp=True,
            full_output=True)
        if fval > 30000:
            raise ValueError('solution has error of %s' % fval)
        return DeviceSettings.fromVector(self.graph, x0)
        
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
        assert isinstance(settings, DeviceSettings)
        layers = []

        for dev, devSettings in settings.byDevice():
            requestedColor = devSettings.getValue(dev, L9['color'])
            candidatePics = [] # (distance, path, picColor)
            for (sample, path), s in self.sampleSettings.items():
                otherDevSettings = s.ofDevice(dev)
                if not otherDevSettings:
                    continue
                dist = devSettings.distanceTo(otherDevSettings)
                log.info('  candidate pic %s %s dist=%s', sample, path, dist)
                candidatePics.append((dist, path, s.getValue(dev, L9['color'])))
            candidatePics.sort()
            # we could even blend multiple top candidates, or omit all
            # of them if they're too far
            bestDist, bestPath, bestPicColor = candidatePics[0]
            log.info('  device best d=%g path=%s color=%s', bestDist, bestPath, bestPicColor)
            
            layers.append({'path': bestPath,
                           'color': colorRatio(requestedColor, bestPicColor)})
        
        return layers
