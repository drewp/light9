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
    return a[:w, :h, :3]


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


class ImageDist(object):

    def __init__(self, img1):
        self.a = img1.reshape((-1,))
        self.d = 255 * 255 * self.a.shape[0]

    def distanceTo(self, img2):
        b = img2.reshape((-1,))
        return 1 - numpy.dot(self.a, b) / self.d


class ImageDistAbs(object):

    def __init__(self, img1):
        self.a = img1
        self.maxDist = img1.shape[0] * img1.shape[1] * img1.shape[2] * 255

    def distanceTo(self, img2):
        return numpy.sum(numpy.absolute(self.a - img2),
                         axis=None) / self.maxDist


class Solver(object):

    def __init__(self, graph, sessions=None, imgSize=(100, 53)):
        self.graph = graph
        self.sessions = sessions  # URIs of capture sessions to load
        self.imgSize = imgSize
        self.samples = {}  # uri: Image array (float 0-255)
        self.fromPath = {}  # imagePath: image array
        self.path = {}  # sample: path
        self.blurredSamples = {}
        self.sampleSettings = {}  # sample: DeviceSettings
        self.samplesForDevice = {}  # dev : [(sample, img)]

    def loadSamples(self):
        """learn what lights do from images"""

        log.info('loading...')

        with self.graph.currentState() as g:
            for sess in self.sessions:
                for cap in g.objects(sess, L9['capture']):
                    self._loadSample(g, cap)
        log.info('loaded %s samples', len(self.samples))

    def _loadSample(self, g, samp):
        pathUri = g.value(samp, L9['imagePath'])
        img = loadNumpy(pathUri.replace(L9[''], '')).astype(float)
        settings = DeviceSettings.fromResource(self.graph, samp)

        self.samples[samp] = img
        self.fromPath[pathUri] = img
        self.blurredSamples[samp] = self._blur(img)

        self.path[samp] = pathUri
        assert samp not in self.sampleSettings
        self.sampleSettings[samp] = settings
        devs = settings.devices()
        if len(devs) == 1:
            self.samplesForDevice.setdefault(devs[0], []).append((samp, img))

    def _blur(self, img):
        return scipy.ndimage.gaussian_filter(img, 10, 0, mode='nearest')

    def draw(self, painting):
        return self._draw(painting, self.imgSize[0], self.imgSize[1])

    def _draw(self, painting, w, h):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()

        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(w / 15)  # ?
        for stroke in painting['strokes']:
            for pt in stroke['pts']:
                op = ctx.move_to if pt is stroke['pts'][0] else ctx.line_to
                op(pt[0] * w, pt[1] * h)

            r, g, b = parseHex(stroke['color'])
            ctx.set_source_rgb(r / 255, g / 255, b / 255)
            ctx.stroke()

        #surface.write_to_png('/tmp/surf.png')
        return numpyFromCairo(surface)

    def bestMatch(self, img, device=None):
        """the one sample that best matches this image"""
        #img = self._blur(img)
        results = []
        dist = ImageDist(img)
        if device is None:
            items = list(self.samples.items())
        else:
            items = self.samplesForDevice[device]
        for uri, img2 in sorted(items):
            if img.shape != img2.shape:
                log.warn("mismatch %s %s", img.shape, img2.shape)
                continue
            results.append((dist.distanceTo(img2), uri, img2))
        results.sort()
        topDist, topUri, topImg = results[0]
        print('tops2')
        for row in results[:4]:
            print('%.5f' % row[0], row[1][-20:], self.sampleSettings[row[1]])

        #saveNumpy('/tmp/best_in.png', img)
        #saveNumpy('/tmp/best_out.png', topImg)
        #saveNumpy('/tmp/mult.png', topImg / 255 * img)
        return topUri, topDist

    def bestMatches(self, img, devices=None):
        """settings for the given devices that point them each
        at the input image"""
        dist = ImageDist(img)
        devSettings = []
        for dev in devices:
            results = []
            for samp, img2 in self.samplesForDevice[dev]:
                results.append((dist.distanceTo(img2), samp))
            results.sort()

            s = self.blendResults([
                (d, self.sampleSettings[samp]) for d, samp in results[:8]
            ])
            devSettings.append(s)
        return DeviceSettings.fromList(self.graph, devSettings)

    def blendResults(self, results):
        """list of (dist, settings)"""

        dists = [d for d, sets in results]
        hi = max(dists)
        lo = min(dists)
        n = len(results)
        remappedDists = [1 - (d - lo) / (hi - lo) * n / (n + 1) for d in dists]
        total = sum(remappedDists)

        #print 'blend'
        #for o,n in zip(dists, remappedDists):
        #    print o,n, n / total
        blend = DeviceSettings.fromBlend(
            self.graph,
            [(d / total, sets) for d, (_, sets) in zip(remappedDists, results)])
        return blend

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
        dist = ImageDist(pic0Blur)
        for sample, picSample in sorted(self.blurredSamples.items()):
            #saveNumpy('/tmp/sample_%s.png' % sample.split('/')[-1],
            #          f(picSample))
            sampleDist[sample] = dist.distanceTo(picSample)
        results = sorted([(d, uri) for uri, d in list(sampleDist.items())])

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

        colorSteps = 2
        colorStep = 1. / colorSteps

        # use toVector then add ranges
        dims = [
            (DEV['aura1'], L9['rx'], [slice(.2, .7 + .1, .2)]),
            (DEV['aura1'], L9['ry'], [slice(.573, .573 + 1, 1)]),
            (DEV['aura1'], L9['color'], [
                slice(0, 1 + colorStep, colorStep),
                slice(0, 1 + colorStep, colorStep),
                slice(0, 1 + colorStep, colorStep)
            ]),
        ]
        deviceAttrFilter = [(d, a) for d, a, s in dims]

        dist = ImageDist(pic0)

        def drawError(x):
            settings = DeviceSettings.fromVector(
                self.graph, x, deviceAttrFilter=deviceAttrFilter)
            preview = self.combineImages(self.simulationLayers(settings))
            #saveNumpy('/tmp/x_%s.png' % abs(hash(settings)), preview)

            out = dist.distanceTo(preview)

            #print 'measure at', x, 'drawError=', out
            return out

        x0, fval, grid, Jout = scipy.optimize.brute(
            func=drawError,
            ranges=sum([s for dev, da, s in dims], []),
            finish=None,
            disp=True,
            full_output=True)
        if fval > 30000:
            raise ValueError('solution has error of %s' % fval)
        return DeviceSettings.fromVector(self.graph,
                                         x0,
                                         deviceAttrFilter=deviceAttrFilter)

    def combineImages(self, layers):
        """make a result image from our self.samples images"""
        out = (next(iter(self.fromPath.values())) * 0).astype(numpy.uint16)
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
            candidatePics = []  # (distance, path, picColor)
            for sample, s in list(self.sampleSettings.items()):
                path = self.path[sample]
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
            log.info('  device best d=%g path=%s color=%s', bestDist, bestPath,
                     bestPicColor)

            layers.append({
                'path': bestPath,
                'color': colorRatio(requestedColor, bestPicColor)
            })

        return layers
