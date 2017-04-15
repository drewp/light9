from light9.namespaces import RDF, L9
from PIL import Image
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
                self.samples[samp] = scipy.misc.fromimage(img, mode='RGB')

    def draw(self, painting, w, h):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        ctx.move_to(0, 0)
        ctx.line_to(100,30)
        
        ctx.set_source_rgb(0.3, 0.2, 0.5)
        ctx.set_line_width(20)
        ctx.stroke()
        # then blur?
        surface.write_to_png('/tmp/surf.png')
                
    def solve(self, painting):
        """
        given strokes of colors on a photo of the stage, figure out the
        best light settings to match the image
        """
        self.draw(painting, 100, 80)
        return 0


    def simulationLayers(self, settings):
        """
        how should a simulation preview approximate the light settings
        (device attribute values) by combining photos we have?
        """
    
