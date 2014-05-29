from __future__ import division
import glob, time, logging, ast, os
from bisect import bisect_left,bisect
import louie as dispatcher
from rdflib import Literal
from light9 import showconfig
from light9.namespaces import L9

from bcf2000 import BCF2000

log = logging.getLogger()
# todo: move to config, consolidate with ascoltami, musicPad, etc
introPad = 4
postPad = 4

class Curve(object):
    """curve does not know its name. see Curveset"""
    def __init__(self):
        self.points = [] # x-sorted list of (x,y)
        self._muted = False

    def __repr__(self):
        return "<%s (%s points)>" % (self.__class__.__name__, len(self.points))

    def muted():
        doc = "Whether to currently send levels (boolean, obviously)"
        def fget(self):
            return self._muted
        def fset(self, val):
            self._muted = val
            dispatcher.send('mute changed', sender=self)
        return locals()
    muted = property(**muted())

    def toggleMute(self):
        self.muted = not self.muted

    def load(self,filename):
        self.points[:]=[]
        for line in file(filename):
            x, y = line.split()
            self.points.append((float(x), ast.literal_eval(y)))
        self.points.sort()
        dispatcher.send("points changed",sender=self)

    def set_from_string(self, pts):
        self.points[:] = []
        vals = pts.split()
        pairs = zip(vals[0::2], vals[1::2])
        for x, y in pairs:
            self.points.append((float(x), ast.literal_eval(y)))
        self.points.sort()
        dispatcher.send("points changed",sender=self)

    def points_as_string(self):
        return ' '.join("%s %r" % p for p in self.points)
        
    def save(self,filename):
        # this is just around for markers, now
        if filename.endswith('-music') or filename.endswith('_music'):
            print "not saving music track"
            return
        f = file(filename,'w')
        for p in self.points:
            f.write("%s %r\n" % p)
        f.close()

    def eval(self, t, allow_muting=True):
        if self.muted and allow_muting:
            return 0
        if not self.points:
            raise ValueError("curve has no points")
        i = bisect_left(self.points,(t,None))-1

        if i == -1:
            return self.points[0][1]
        if self.points[i][0]>t:
            return self.points[i][1]
        if i>=len(self.points)-1:
            return self.points[i][1]

        p1,p2 = self.points[i],self.points[i+1]
        frac = (t-p1[0])/(p2[0]-p1[0])
        y = p1[1]+(p2[1]-p1[1])*frac
        return y
    __call__=eval

    def insert_pt(self, new_pt):
        """returns index of new point"""
        i = bisect(self.points, (new_pt[0],None))
        self.points.insert(i,new_pt)
        # missing a check that this isn't the same X as the neighbor point
        return i

    def set_points(self, updates):
        for i, pt in updates:
            self.points[i] = pt
            
        x = None
        for p in self.points:
            if p[0] <= x:
                raise ValueError("overlapping points")
            x = p[0]

    def pop_point(self, i):
        return self.points.pop(i)
            
    def remove_point(self, pt):
        self.points.remove(pt)
            
    def indices_between(self, x1, x2, beyond=0):
        leftidx = max(0, bisect(self.points, (x1,None)) - beyond)
        rightidx = min(len(self.points),
                       bisect(self.points, (x2,None)) + beyond)
        return range(leftidx, rightidx)
        
    def points_between(self, x1, x2):
        return [self.points[i] for i in self.indices_between(x1,x2)]

    def point_before(self, x):
        """(x,y) of the point left of x, or None"""
        leftidx = self.index_before(x)
        if leftidx is None:
            return None
        return self.points[leftidx]

    def index_before(self, x):
        leftidx = bisect(self.points, (x,None)) - 1
        if leftidx < 0:
            return None
        return leftidx

class Markers(Curve):
    """Marker is like a point but the y value is a string"""
    def eval(self):
        raise NotImplementedError()
    

def slope(p1,p2):
    if p2[0] == p1[0]:
        return 0
    return (p2[1] - p1[1]) / (p2[0] - p1[0])


class Sliders(BCF2000):
    def __init__(self, cb, knobCallback, knobButtonCallback):
        BCF2000.__init__(self)
        self.cb = cb
        self.knobCallback = knobCallback
        self.knobButtonCallback = knobButtonCallback
    def valueIn(self, name, value):
        if name.startswith("slider"):
            self.cb(int(name[6:]), value / 127)
        if name.startswith("knob"):
            self.knobCallback(int(name[4:]), value / 127)
        if name.startswith("button-knob"):
            self.knobButtonCallback(int(name[11:]))

        
class Curveset(object):
    curves = None # curvename : curve
    def __init__(self, graph, session, sliders=False):
        """sliders=True means support the hardware sliders"""
        self.graph, self.session = graph, session

        self.currentSong = None
        self.curves = {} # name (str) : Curve
        self.curveName = {} # reverse
        
        self.sliderCurve = {} # slider number (1 based) : curve name
        self.sliderNum = {} # reverse
        if sliders:
            self.sliders = Sliders(self.hw_slider_in, self.hw_knob_in, 
                                   self.hw_knob_button)
            dispatcher.connect(self.curvesToSliders, "curves to sliders")
            dispatcher.connect(self.knobOut, "knob out")
            self.lastSliderTime = {} # num : time
            self.sliderSuppressOutputUntil = {} # num : time
            self.sliderIgnoreInputUntil = {}
        else:
            self.sliders = None
        self.markers = Markers()

        graph.addHandler(self.loadCurvesForSong)

    def loadCurvesForSong(self):
        """
        current curves will track song's curves.
        
        This fires 'add_curve' dispatcher events to announce the new curves.
        """
        log.info('loadCurvesForSong')
        dispatcher.send("clear_curves")
        self.curves.clear()
        self.curveName.clear()
        self.sliderCurve.clear()
        self.sliderNum.clear()
        self.markers = Markers()
        
        self.currentSong = self.graph.value(self.session, L9['currentSong'])
        if self.currentSong is None:
            return

        for uri in self.graph.objects(self.currentSong, L9['curve']):
            c = Curve()
            c.uri = uri
            pts = self.graph.value(uri, L9['points'])
            if pts is not None:
                c.set_from_string(pts)
                c.pointsStorage = 'graph'
            else:
                diskPts = self.graph.value(uri, L9['pointsFile'])
                c.load(os.path.join(showconfig.curvesDir(), diskPts))
                c.pointsStorage = 'file'

            curvename = self.graph.label(uri)
            if not curvename:
                raise ValueError("curve %r has no label" % uri)
            self.add_curve(curvename, c)

        basename = os.path.join(
            showconfig.curvesDir(),
            showconfig.songFilenameFromURI(self.currentSong))
        try:
            self.markers.load("%s.markers" % basename)
        except IOError:
            print "no marker file found"
            
    def save(self):
        """writes a file for each curve with a name
        like basename-curvename, or saves them to the rdf graph"""
        basename=os.path.join(
            showconfig.curvesDir(),
            showconfig.songFilenameFromURI(self.currentSong))

        patches = []
        for label, curve in self.curves.items():
            if curve.pointsStorage == 'file':
                log.warn("not saving file curves anymore- skipping %s" % label)
                #cur.save("%s-%s" % (basename,name))
            elif curve.pointsStorage == 'graph':
                ctx = self.currentSong
                patches.append(self.graph.getObjectPatch(
                    ctx,
                    subject=curve.uri,
                    predicate=L9['points'],
                    newObject=Literal(curve.points_as_string())))
            else:
                raise NotImplementedError(curve.pointsStorage)

        self.markers.save("%s.markers" % basename)
        # this will cause reloads that will clear our curve list
        for p in patches:
            self.graph.patch(p)

    def sorter(self, name):
        return (not name in ['music', 'smooth_music'], name)
        
    def curveNamesInOrder(self):
        return sorted(self.curves.keys(), key=self.sorter)
            
    def add_curve(self, name, curve):
        # should be indexing by uri
        if isinstance(name, Literal):
            name = str(name) 
        if name in self.curves:
            raise ValueError("can't add a second curve named %r" % name)
        self.curves[name] = curve
        self.curveName[curve] = name

        if self.sliders and name not in ['smooth_music', 'music']:
            num = len(self.sliderCurve) + 1
            if num <= 8:
                self.sliderCurve[num] = name
                self.sliderNum[name] = num
            else:
                num = None
        else:
            num = None
            
        dispatcher.send("add_curve", slider=num, knobEnabled=num is not None,
                        sender=self, name=name)

    def globalsdict(self):
        return self.curves.copy()
    
    def get_time_range(self):
        return 0, dispatcher.send("get max time")[0][1]

    def new_curve(self, name, renameIfExisting=True):
        if isinstance(name, Literal):
            name = str(name)
        if name=="":
            print "no name given"
            return
        if not renameIfExisting and name in self.curves:
            return
        while name in self.curves:
           name=name+"-1"

        c = Curve()
        # missing some new attrs here, uri pointsStorage
        s,e = self.get_time_range()
        c.points.extend([(s,0), (e,0)])
        self.add_curve(name,c)

    def hw_slider_in(self, num, value):
        try:
            curve = self.curves[self.sliderCurve[num]]
        except KeyError:
            return

        now = time.time()
        if now < self.sliderIgnoreInputUntil.get(num):
            return
        # don't make points too fast. This is the minimum spacing
        # between slider-generated points.
        self.sliderIgnoreInputUntil[num] = now + .1
        
        # don't push back on the slider for a little while, since the
        # user might be trying to slowly move it. This should be
        # bigger than the ignore time above.
        self.sliderSuppressOutputUntil[num] = now + .2
        
        dispatcher.send("set key", curve=curve, value=value)

    def hw_knob_in(self, num, value):
        try:
            curve = self.curves[self.sliderCurve[num]]
        except KeyError:
            return
        dispatcher.send("knob in", curve=curve, value=value)

    def hw_knob_button(self, num):
        try:
            curve = self.curves[self.sliderCurve[num]]
        except KeyError:
            return

        dispatcher.send("set key", curve=curve)
        

    def curvesToSliders(self, t):
        now = time.time()
        for num, name in self.sliderCurve.items():
            if now < self.sliderSuppressOutputUntil.get(num):
                continue
#            self.lastSliderTime[num] = now
            
            value = self.curves[name].eval(t)
            self.sliders.valueOut("slider%s" % num, value * 127)

    def knobOut(self, curve, value):
        try:
            num = self.sliderNum[self.curveName[curve]]
        except KeyError:
            return
        self.sliders.valueOut("knob%s" % num, value * 127)
