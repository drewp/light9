from __future__ import division
import math, logging, traceback
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GooCanvas
import louie as dispatcher
from rdflib import Literal
from twisted.internet import reactor
from light9.curvecalc.zoomcontrol import RegionZoom
from light9.curvecalc import cursors
from light9.curvecalc.curve import introPad, postPad
from lib.goocanvas_compat import Points, polyline_new_line

log = logging.getLogger()
print "curveview.py toplevel"
def vlen(v):
    return math.sqrt(v[0]*v[0] + v[1]*v[1])

def angle_between(base, p0, p1):
    p0 = p0[0] - base[0], p0[1] - base[1]
    p1 = p1[0] - base[0], p1[1] - base[1]
    p0 = [x/vlen(p0) for x in p0]
    p1 = [x/vlen(p1) for x in p1]
    dot = p0[0]*p1[0]+p0[1]*p1[1]
    dot = max(-1,min(1,dot))
    return math.degrees(math.acos(dot))

class Sketch:
    """a sketch motion on a curveview, with temporary points while you
    draw, and simplification when you release"""
    
    def __init__(self,curveview,ev):
        self.curveview = curveview
        self.pts = []
        self.last_x = None

    def motion(self,ev):
        p = self.curveview.world_from_screen(ev.x, ev.y)
        p = p[0], max(0,min(1,p[1]))
        if self.last_x is not None and abs(ev.x - self.last_x) < 4:
            return
        self.last_x = ev.x
        self.pts.append(p)
        self.curveview.add_point(p)

    def release(self,ev):
        pts = self.pts
        pts.sort()
        finalPoints = pts[:]

        dx = .01
        to_remove = []
        for i in range(1,len(pts)-1):
            x = pts[i][0]

            p_left = (x - dx, self.curveview.curve(x - dx))
            p_right = (x + dx, self.curveview.curve(x + dx))

            if angle_between(pts[i], p_left, p_right) > 160:
                to_remove.append(i)

        for i in to_remove:
            self.curveview.curve.remove_point(pts[i])
            finalPoints.remove(pts[i])

        # the simplified curve may now be too far away from some of
        # the points, so we'll put them back. this has an unfortunate
        # bias toward reinserting the earlier points
        for i in to_remove:
            p = pts[i]
            if abs(self.curveview.curve(p[0]) - p[1]) > .1:
                self.curveview.add_point(p)
                finalPoints.append(p)
            
        self.curveview.update_curve()
        self.curveview.select_points(finalPoints)

class SelectManip(object):
    """
    selection manipulator is created whenever you have a selection. It
    draws itself on the canvas and edits the points when you drag
    various parts
    """
    def __init__(self, parent, getSelectedIndices, getWorldPoint,
                 getScreenPoint, getCanvasHeight, setPoints,
                 getWorldTime, getWorldValue, getDragRange):
        """parent goocanvas group"""
        self.getSelectedIndices = getSelectedIndices
        self.getWorldPoint = getWorldPoint
        self.getScreenPoint = getScreenPoint
        self.getCanvasHeight = getCanvasHeight
        self.setPoints = setPoints
        self.getWorldTime = getWorldTime
        self.getDragRange = getDragRange
        self.getWorldValue = getWorldValue
        self.grp = GooCanvas.CanvasGroup(parent=parent)
        
        self.title = GooCanvas.CanvasText(parent=self.grp, text="selectmanip",
                                    x=10, y=10, fill_color='white', font="ubuntu 10")

        self.bbox = GooCanvas.CanvasRect(parent=self.grp,
                                   fill_color_rgba=0xffff0030,
                                   line_width=0)

        self.xTrans = polyline_new_line(parent=self.grp, close_path=True,
                                         fill_color_rgba=0xffffff88,
                                         )
        self.centerScale = polyline_new_line(parent=self.grp, close_path=True,
                                              fill_color_rgba=0xffffff88,
                                         )

        thickLine = lambda: polyline_new_line(parent=self.grp,
                                               stroke_color_rgba=0xffffccff,
                                               line_width=6)
        self.leftScale = thickLine()
        self.rightScale = thickLine()
        self.topScale = thickLine()
        
        for grp, name in [(self.xTrans, 'x'),
                          (self.leftScale, 'left'),
                          (self.rightScale, 'right'),
                          (self.topScale, 'top'),
                          (self.centerScale, 'centerScale'),
                          ]:
            grp.connect("button-press-event", self.onPress, name)
            grp.connect("button-release-event", self.onRelease, name)
            grp.connect("motion-notify-event", self.onMotion, name)
            grp.connect("enter-notify-event", self.onEnter, name)
            grp.connect("leave-notify-event", self.onLeave, name)
            # and hover highlight
        self.update()

    def onEnter(self, item, target_item, event, param):
        self.prevColor = item.props.stroke_color_rgba
        item.props.stroke_color_rgba = 0xff0000ff
        
    def onLeave(self, item, target_item, event, param):
        item.props.stroke_color_rgba = self.prevColor
        
    def onPress(self, item, target_item, event, param):
        self.dragStartTime = self.getWorldTime(event.x)
        idxs = self.getSelectedIndices()

        self.origPoints = [self.getWorldPoint(i) for i in idxs]
        self.origMaxValue = max(p[1] for p in self.origPoints)
        moveLeft, moveRight = self.getDragRange(idxs)

        if param == 'centerScale':
            self.maxPointMove = min(moveLeft, moveRight)
        
        self.dragRange = (self.dragStartTime - moveLeft,
                          self.dragStartTime + moveRight)
        return True

    def onMotion(self, item, target_item, event, param):
        if hasattr(self, 'dragStartTime'):
            origPts = zip(self.getSelectedIndices(), self.origPoints)
            left = origPts[0][1][0]
            right = origPts[-1][1][0]
            width = right - left
            dontCross = .001

            clampLo = left if param == 'right' else self.dragRange[0]
            clampHi = right if param == 'left' else self.dragRange[1]

            def clamp(x, lo, hi):
                return max(lo, min(hi, x))
            
            mouseT = self.getWorldTime(event.x)
            clampedT = clamp(mouseT, clampLo + dontCross, clampHi - dontCross)

            dt = clampedT - self.dragStartTime

            if param == 'x':
                self.setPoints((i, (orig[0] + dt, orig[1]))
                               for i, orig in origPts)
            elif param == 'left':
                self.setPoints((
                    i,
                    (left + dt +
                     (orig[0] - left) / width *
                     clamp(width - dt, dontCross, right - clampLo - dontCross),
                     orig[1])) for i, orig in origPts)
            elif param == 'right':
                self.setPoints((
                    i,
                    (left +
                     (orig[0] - left) / width *
                     clamp(width + dt, dontCross, clampHi - left - dontCross),
                     orig[1])) for i, orig in origPts)
            elif param == 'top':
                v = self.getWorldValue(event.y)
                if self.origMaxValue == 0:
                    self.setPoints((i, (orig[0], v)) for i, orig in origPts)
                else:
                    scl = max(0, min(1 / self.origMaxValue,
                                     v / self.origMaxValue))
                    self.setPoints((i, (orig[0], orig[1] * scl))
                                   for i, orig in origPts)

            elif param == 'centerScale':
                dt = mouseT - self.dragStartTime
                rad = width / 2
                tMid = left + rad
                maxScl = (rad + self.maxPointMove - dontCross) / rad
                newWidth = max(dontCross / width,
                               min((rad + dt) / rad, maxScl)) * width
                self.setPoints((i,
                                (tMid +
                                 ((orig[0] - left) / width - .5) * newWidth,
                                 orig[1])) for i, orig in origPts)
                

    def onRelease(self, item, target_item, event, param):
        if hasattr(self, 'dragStartTime'):
            del self.dragStartTime

    def update(self):
        """if the view or selection or selected point positions
        change, call this to redo the layout of the manip"""
        idxs = self.getSelectedIndices()
        pts = [self.getScreenPoint(i) for i in idxs]
        
        b = self.bbox.props
        b.x = min(p[0] for p in pts) - 5
        b.y = min(p[1] for p in pts) - 5
        margin = 10 if len(pts) > 1 else 0
        b.width = max(p[0] for p in pts) - b.x + margin
        b.height = min(max(p[1] for p in pts) - b.y + margin,
                       self.getCanvasHeight() - b.y - 1)

        multi = (GooCanvas.CanvasItemVisibility.VISIBLE if len(pts) > 1 else
                 GooCanvas.CanvasItemVisibility.INVISIBLE)
        b.visibility = multi
        self.leftScale.props.visibility = multi
        self.rightScale.props.visibility = multi
        self.topScale.props.visibility = multi
        self.centerScale.props.visibility = multi

        self.title.props.text = "%s %s selected" % (
            len(idxs), "point" if len(idxs) == 1 else "points")

        centerX = b.x + b.width / 2

        midY = self.getCanvasHeight() * .5
        loY = self.getCanvasHeight() * .8

        self.leftScale.props.points = Points([
            (b.x, b.y), (b.x, b.y + b.height)])
        self.rightScale.props.points = Points([
            (b.x + b.width, b.y), (b.x + b.width, b.y + b.height)])

        self.topScale.props.points = Points([
            (b.x, b.y), (b.x + b.width, b.y)])

        self.updateXTrans(centerX, midY)

        self.centerScale.props.points = Points([
            (centerX - 5, loY - 5),
            (centerX + 5, loY - 5),
            (centerX + 5, loY + 5),
            (centerX - 5, loY + 5)])
            

    def updateXTrans(self, centerX, midY):       
        x1 = centerX - 30
        x2 = centerX - 20
        x3 = centerX + 20
        x4 = centerX + 30
        y1 = midY - 10
        y2 = midY - 5
        y3 = midY + 5
        y4 = midY + 10
        shape = [
            (x1, midY), # left tip
            (x2, y1),
            (x2, y2),
            
            (x3, y2),
            (x3, y1),
            (x4, midY), # right tip
            (x3, y4),
            (x3, y3),
            
            (x2, y3),
            (x2, y4)
            ]

        self.xTrans.props.points = Points(shape)

    def destroy(self):
        self.grp.remove()

class Curveview(object):
    """
    graphical curve widget only. Please pack .widget

    <caller's parent>
     -> self.widget <caller packs this>
       -> EventBox
         -> Box vertical, for border
           -> self.canvas GooCanvas
             -> root CanvasItem
               ..various groups and items..

    The canvas x1/x2/y1/y2 coords are updated to match self.widget.
    
    """
    def __init__(self, curve, markers, knobEnabled=False, isMusic=False,
                 zoomControl=None):
        """knobEnabled=True highlights the previous key and ties it to a
        hardware knob"""
        self.curve = curve
        self.markers = markers
        self.knobEnabled = knobEnabled
        self._isMusic = isMusic
        self.zoomControl = zoomControl
        
        self.redrawsEnabled = False

        box = self.createOuterWidgets()
        self.canvas = self.createCanvasWidget(box)
        self.trackWidgetSize()
        self.update_curve()
        
        self._time = -999
        self.last_mouse_world = None
        self.entered = False # is the mouse currently over this widget
        self.selected_points=[] # idx of points being dragged
        self.dots = {}
        # self.bind("<Enter>",self.focus)
        dispatcher.connect(self.playPause, "onPlayPause")
        dispatcher.connect(self.input_time, "input time")
        dispatcher.connect(self.update_curve, "zoom changed")
        dispatcher.connect(self.update_curve, "points changed",
                           sender=self.curve)
        dispatcher.connect(self.update_curve, "mute changed", 
                           sender=self.curve)
        dispatcher.connect(self.select_between, "select between")
        dispatcher.connect(self.acls, "all curves lose selection")
        if self.knobEnabled:
            dispatcher.connect(self.knob_in, "knob in")
            dispatcher.connect(self.slider_in, "set key")


        # todo: hold control to get a [+] cursor
        #        def curs(ev):
        #            print ev.state
        #        self.bind("<KeyPress>",curs)
        #        self.bind("<KeyRelease-Control_L>",lambda ev: curs(0))
      
        # this binds on c-a-b1, etc
        if 0: # unported
            self.regionzoom = RegionZoom(self, self.world_from_screen,
                                         self.screen_from_world)

        self.sketch = None # an in-progress sketch

        self.dragging_dots = False
        self.selecting = False

    def acls(self, butNot=None):
        if butNot is self:
            return
        self.unselect()

    def createOuterWidgets(self):
        self.timelineLine = self.curveGroup = self.selectManip = None
        self.widget = Gtk.EventBox()
        self.widget.set_can_focus(True)
        self.widget.add_events(Gdk.EventMask.KEY_PRESS_MASK |
                               Gdk.EventMask.FOCUS_CHANGE_MASK)
        self.onFocusOut()

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        box.set_border_width(1)
        self.widget.add(box)
        box.show()
        return box

    def trackWidgetSize(self):
        """
        Also tried:

            visibility-notify-event
            (Gdk.EventMask.VISIBILITY_NOTIFY_MASK) fires on some
            resizes but definitely not all. During window resizes,
            sometimes I have to 'shake' the window size to get all
            curves to update.
        
            configure-event seems to never fire.

            size-allocate seems right but i get into infinite bounces
            between two sizes
        """
        def sizeEvent(w, alloc):
            p = self.canvas.props
            if (alloc.width, alloc.height) != (p.x2, p.y2):
                p.x1, p.x2 = 0, alloc.width
                p.y1, p.y2 = 0, alloc.height
                # calling update_curve in this event usually doesn't work
                reactor.callLater(0, self.update_curve)
            return False
            
        #self.widget.connect('size-allocate', sizeEvent) # see docstring

        def visEvent(w, alloc):
            self.setCanvasToWidgetSize()
            return False
        self.widget.add_events(Gdk.EventMask.VISIBILITY_NOTIFY_MASK)
        self.widget.connect('visibility-notify-event', visEvent)

    def setCanvasToWidgetSize(self):
        p = self.canvas.props
        w = self.widget.get_allocated_width()
        h = self.widget.get_allocated_height()
        if (w, h) != (p.x2, p.y2):
            p.x1, p.x2 = 0, w
            p.y1, p.y2 = 0, h
            self.update_curve()

    def createCanvasWidget(self, parent):
        # this is only separate from createOuterWidgets because in the
        # past, i worked around display bugs by recreating the whole
        # canvas widget. If that's not necessary, this could be more
        # clearly combined with createOuterWidgets since there's no
        # time you'd want that one but not this one.
        canvas = GooCanvas.Canvas()
        parent.pack_start(canvas, expand=True, fill=True, padding=0)
        canvas.show()

        p = canvas.props
        p.background_color = 'black'
        root = canvas.get_root_item()

        canvas.connect("leave-notify-event", self.onLeave)
        canvas.connect("enter-notify-event", self.onEnter)
        canvas.connect("motion-notify-event", self.onMotion)
        canvas.connect("scroll-event", self.onScroll)
        canvas.connect("button-release-event", self.onRelease)
        root.connect("button-press-event", self.onCanvasPress)

        self.widget.connect("key-press-event", self.onKeyPress)

        self.widget.connect("focus-in-event", self.onFocusIn)
        self.widget.connect("focus-out-event", self.onFocusOut)
        #self.widget.connect("event", self.onAny)
        return canvas

    def onAny(self, w, event):
        print "   %s on %s" % (event, w)
        
    def onFocusIn(self, *args):
        dispatcher.send('curve row focus change')     
        dispatcher.send("all curves lose selection", butNot=self)

        self.widget.modify_bg(Gtk.StateFlags.NORMAL, Gdk.color_parse("red"))

    def onFocusOut(self, widget=None, event=None):
        dispatcher.send('curve row focus change')                  
        self.widget.modify_bg(Gtk.StateFlags.NORMAL, Gdk.color_parse("gray30"))

        # you'd think i'm unselecting when we lose focus, but we also
        # lose focus when the user moves off the toplevel window, and
        # that's not a time to forget the selection. See the 'all
        # curves lose selection' signal for the fix.

    def onKeyPress(self, widget, event):
        if event.string in list('12345'):
            x = int(event.string)
            self.add_point((self.current_time(), (x - 1) / 4.0))
        if event.string in list('qwerty'):
            self.add_marker((self.current_time(), event.string))

    def onDelete(self):
        if self.selected_points:
            self.remove_point_idx(*self.selected_points)
        
            
    def onCanvasPress(self, item, target_item, event):
        # when we support multiple curves per canvas, this should find
        # the close one and add a point to that. Binding to the line
        # itself is probably too hard to hit. Maybe a background-color
        # really thick line would be a nice way to allow a sloppier
        # click

        self.widget.grab_focus()

        _, flags = event.get_state()
        if flags & Gdk.ModifierType.CONTROL_MASK:
            self.new_point_at_mouse(event)
        elif flags & Gdk.ModifierType.SHIFT_MASK:
            self.sketch_press(event)
        else:
            self.select_press(event)

        # this stops some other handler that wants to unfocus 
        return True

    def playPause(self):
        """
        user has pressed ctrl-p over a curve view, possibly this
        one. Returns the time under the mouse if we know it, or else
        None

        todo: there should be a faint timecursor line under the mouse
        so it's more obvious that we use that time for some
        events. Rt-click should include Ctrl+P as 'play/pause from
        here'
        """
        # maybe self.canvas.get_pointer would be ok for this? i didn't try it
        if self.entered and hasattr(self, 'lastMouseX'):
            t = self.world_from_screen(self.lastMouseX, 0)[0]
            return t
        return None

    def goLive(self):
        """this is for startup performance only, since the curves were
        getting redrawn many times. """
        self.redrawsEnabled = True
        self.update_curve()

    def knob_in(self, curve, value):
        """user turned a hardware knob, which edits the point to the
        left of the current time"""
        if curve != self.curve:
            return
        idx = self.curve.index_before(self.current_time())
        if idx is not None:
            pos = self.curve.points[idx]
            self.curve.set_points([(idx, (pos[0], value))])

    def slider_in(self, curve, value=None):
        """user pushed on a slider. make a new key.  if value is None,
        the value will be the same as the last."""
        if curve != self.curve:
            return

        if value is None:
            value = self.curve.eval(self.current_time())

        self.curve.insert_pt((self.current_time(), value))

    def print_state(self, msg=""):
        if 0:
            print "%s: dragging_dots=%s selecting=%s" % (
                msg, self.dragging_dots, self.selecting)

    def select_points(self, pts):
        """set selection to the given point values (tuples, not indices)"""
        idxs = []
        for p in pts:
            idxs.append(self.curve.points.index(p))
        self.select_indices(idxs)

    def select_indices(self, idxs):
        """set selection to these point indices. This is the only
        writer to self.selected_points"""
        self.selected_points = idxs
        self.highlight_selected_dots()
        if self.selected_points and not self.selectManip:
            self.selectManip = SelectManip(
                self.canvas.get_root_item(),
                getSelectedIndices=lambda: sorted(self.selected_points),
                getWorldPoint=lambda i: self.curve.points[i],
                getScreenPoint=lambda i: self.screen_from_world(self.curve.points[i]),
                getWorldTime=lambda x: self.world_from_screen(x, 0)[0],
                getWorldValue=lambda y: self.world_from_screen(0, y)[1],
                getCanvasHeight=lambda: self.canvas.props.y2,
                setPoints=self.setPoints,
                getDragRange=self.getDragRange,
                )
        if not self.selected_points and self.selectManip:
            self.selectManip.destroy()
            self.selectManip = None

        self.selectionChanged()

    def getDragRange(self, idxs):
        """
        if you're dragging these points, what's the most time you can move
        left and right before colliding (exactly) with another
        point
        """
        maxLeft = maxRight = 99999
        cp = self.curve.points
        for i in idxs:
            nextStatic = i
            while nextStatic >= 0 and nextStatic in idxs:
                nextStatic -= 1
            if nextStatic >= 0:
                maxLeft = min(maxLeft, cp[i][0] - cp[nextStatic][0])

            nextStatic = i
            while nextStatic <= len(cp) - 1 and nextStatic in idxs:
                nextStatic += 1
            if nextStatic <= len(cp) - 1:
                maxRight = min(maxRight, cp[nextStatic][0] - cp[i][0])
        return maxLeft, maxRight

    def setPoints(self, updates):
        self.curve.set_points(updates)
        
    def selectionChanged(self):
        if self.selectManip:
            self.selectManip.update()

    def select_press(self,ev):
        # todo: these select_ handlers are getting called on c-a-drag
        # zooms too. the dispatching should be more selective than
        # just calling both handlers all the time
        self.print_state("select_press")
        if self.dragging_dots:
            return
        if not self.selecting:
            self.selecting = True
            self.select_start = self.world_from_screen(ev.x,0)[0]
            #cursors.push(self,"gumby")
        
    def select_motion(self,ev):
        if not self.selecting:
            return
        start = self.select_start
        cur = self.world_from_screen(ev.x, 0)[0]
        self.select_between(start, cur)
        
    def select_release(self,ev):
        self.print_state("select_release")

        # dotrelease never gets called, but I can clear that state here
        self.dragging_dots = False
        
        if not self.selecting:
            return
        #cursors.pop(self)
        self.selecting = False
        self.select_between(self.select_start,
                            self.world_from_screen(ev.x,0)[0])

    def sketch_press(self,ev):
        self.sketch = Sketch(self,ev)

    def sketch_motion(self,ev):
        if self.sketch:
            self.sketch.motion(ev)

    def sketch_release(self,ev):
        if self.sketch:
            self.sketch.release(ev)
            self.sketch = None

    def current_time(self):
        return self._time

    def _coords(self):
        z = self.zoomControl
        ht = self.canvas.props.y2
        marginBottom = 3 if ht > 40 else 0
        marginTop = marginBottom
        return z, ht, marginBottom, marginTop
        
    def screen_from_world(self,p):
        z, ht, marginBottom, marginTop = self._coords()
        return ((p[0] - z.start) / (z.end - z.start) * self.canvas.props.x2,
                (ht - marginBottom) - p[1] * (ht - (marginBottom + marginTop)))

    def world_from_screen(self,x,y):
        z, ht, marginBottom, marginTop = self._coords()
        return (x / self.canvas.props.x2 * (z.end - z.start) + z.start,
                ((ht - marginBottom) - y) / (ht - (marginBottom + marginTop)))

    def input_time(self, val, forceUpdate=False):
        if self._time == val:
            return
        self.update_time_bar(val)

    def alive(self):
        # Some handlers still run after a view is destroyed, which
        # leads to crashes in somewhere like
        # goocanvas_add_item. Workaround is to disable certain methods
        # when the widget is gone. Correct solution would be to stop
        # and free those handlers when the widget is gone.
        return self.canvas.is_visible()
        
    def update_time_bar(self, t):
        if not self.alive():
            return
        if not getattr(self, 'timelineLine', None):
            self.timelineGroup = GooCanvas.CanvasGroup(
                parent=self.canvas.get_root_item())
            self.timelineLine = polyline_new_line(
                parent=self.timelineGroup,
                points=Points([(0,0), (0,0)]),
                line_width=2, stroke_color='red')

        try:
            pts = [self.screen_from_world((t, 0)),
                   self.screen_from_world((t, 1))]
        except ZeroDivisionError:
            pts = [(-1, -1), (-1, -1)]
        self.timelineLine.set_property('points', Points(pts))
        
        self._time = t
        if self.knobEnabled:
            self.delete('knob')
            prevKey = self.curve.point_before(t)
            if prevKey is not None:
                pos = self.screen_from_world(prevKey)
                self.create_oval(pos[0] - 8, pos[1] - 8,
                                 pos[0] + 8, pos[1] + 8,
                                 outline='#800000',
                                 tags=('knob',))
                dispatcher.send("knob out", value=prevKey[1], curve=self.curve)

    def update_curve(self, *args):
        if not getattr(self, '_pending_update', False):
            self._pending_update = True
            reactor.callLater(.01, self._update_curve)
        
    def _update_curve(self):
        try:
            self._update_curve2()
        except Exception:
            log.error("in update_curve on %s", self.curve.uri)
            raise

    def _update_curve2(self):
        if not getattr(self, '_pending_update', False):
            return
        self._pending_update = False
        if not self.alive():
            return
        if not self.redrawsEnabled:
            print "no redrawsEnabled, skipping", self
            return

        visible_x = (self.world_from_screen(0,0)[0],
                     self.world_from_screen(self.canvas.props.x2, 0)[0])

        visible_idxs = self.curve.indices_between(visible_x[0], visible_x[1],
                                                  beyond=1)
        visible_points = [self.curve.points[i] for i in visible_idxs]
        
        if getattr(self, 'curveGroup', None):
            self.curveGroup.remove()
        self.curveGroup = GooCanvas.CanvasGroup(parent=self.canvas.get_root_item())
        self.curveGroup.lower(None)

        self.canvas.set_property("background-color",
                                 "gray20" if self.curve.muted else "black")

        self.update_time_bar(self._time)
        self._draw_line(visible_points, area=True)
        self._draw_markers(
            self.markers.points[i] for i in
            self.markers.indices_between(visible_x[0], visible_x[1]))
        if self.canvas.props.y2 > 80:
            self._draw_time_tics(visible_x)

            self.dots = {} # idx : canvas rectangle

            if len(visible_points) < 50 and not self.curve.muted:
                self._draw_handle_points(visible_idxs,visible_points)

        self.selectionChanged()

    def is_music(self):
        """are we one of the music curves (which might be drawn a bit
        differently)"""
        return self._isMusic

    def _draw_markers(self, pts):
        colorMap = {
            'q':'#598522',
            'w':'#662285',
            'e':'#852922',
            'r':'#85225C',
            't':'#856B22',
            'y':'#227085',
            }
        for t, name in pts:
            x = int(self.screen_from_world((t,0))[0]) + .5
            polyline_new_line(self.curveGroup,
                              x, 0, x, self.canvas.props.y2,
                              line_width=.4 if name in 'rty' else .8,
                              stroke_color=colorMap.get(name, 'gray'))

    def _draw_time_tics(self,visible_x):
        tic = self._draw_one_tic

        tic(0, "0")
        t1,t2=visible_x
        if t2-t1<30:
            for t in range(int(t1),int(t2)+1):
                tic(t,str(t))
        tic(introPad, str(introPad))

        endtimes = dispatcher.send("get max time")
        if endtimes:
            endtime = endtimes[0][1]
            tic(endtime, "end %.1f"%endtime)
            tic(endtime - postPad, "post %.1f" % (endtime - postPad))
        
    def _draw_one_tic(self,t,label):
        try:
            x = self.screen_from_world((t,0))[0]
            if not 0 <= x < self.canvas.props.x2:
                return
            x = max(5, x) # cheat left-edge stuff onscreen
        except ZeroDivisionError:
            x = -100
            
        ht = self.canvas.props.y2
        polyline_new_line(self.curveGroup,
                                    x, ht,
                                    x, ht - 20,
                                    line_width=.5,
                                    stroke_color='gray70')
        GooCanvas.CanvasText(parent=self.curveGroup,
                       fill_color="white",
                       anchor=GooCanvas.CanvasAnchorType.SOUTH,
                       font="ubuntu 7",
                       x=x+3, y=ht-20,
                       text=label)

    def _draw_line(self, visible_points, area=False):
        if not visible_points:
            return
        linepts=[]
        step=1
        linewidth = 1.5
        maxPointsToDraw = self.canvas.props.x2 / 2
        if len(visible_points) > maxPointsToDraw:
            step = int(len(visible_points) / maxPointsToDraw)
            linewidth = .8
        for p in visible_points[::step]:
            try:
                x,y = self.screen_from_world(p)
            except ZeroDivisionError:
                x = y = -100
            linepts.append((int(x) + .5, int(y) + .5))

        if self.curve.muted:
            fill = 'grey34'
        else:
            fill = 'white'

        if area:
            try:
                base = self.screen_from_world((0, 0))[1]
            except ZeroDivisionError:
                base = -100
            base = base + linewidth / 2
            areapts = linepts[:]
            if len(areapts) >= 1:
                areapts.insert(0, (0, areapts[0][1]))
                areapts.append((self.canvas.props.x2, areapts[-1][1]))
            polyline_new_line(parent=self.curveGroup,
                              points=Points(
                                  [(areapts[0][0], base)] +
                                  areapts +
                                  [(areapts[-1][0], base)]),
                              close_path=True,
                              line_width=0,
                              # transparent as a workaround for
                              # covering some selectmanips (which
                              # become unclickable)
                              fill_color_rgba=0x00800080,
            )

        self.pl = polyline_new_line(parent=self.curveGroup,
                                     points=Points(linepts),
                                     line_width=linewidth,
                                     stroke_color=fill,
                                     )
                
            
    def _draw_handle_points(self,visible_idxs,visible_points):
        for i,p in zip(visible_idxs,visible_points):
            rad=6
            worldp = p
            try:
                p = self.screen_from_world(p)
            except ZeroDivisionError:
                p = (-100, -100)
            dot = GooCanvas.CanvasRect(parent=self.curveGroup,
                                 x=int(p[0] - rad) + .5,
                                 y=int(p[1] - rad) + .5,
                                 width=rad * 2, height=rad * 2,
                                 stroke_color='gray90',
                                 fill_color='blue',
                                 line_width=1,
                                 #tags=('curve','point', 'handle%d' % i)
                                 )

            if worldp[1] == 0:
                rad += 3
                GooCanvas.CanvasEllipse(parent=self.curveGroup,
                                  center_x=p[0],
                                  center_y=p[1],
                                  radius_x=rad,
                                  radius_y=rad,
                                  line_width=2,
                                  stroke_color='#00a000',
                                  #tags=('curve','point', 'handle%d' % i)
                                  )
            dot.connect("button-press-event", self.dotpress, i)
            #self.tag_bind('handle%d' % i,"<ButtonPress-1>",
            #              lambda ev,i=i: self.dotpress(ev,i))
            #self.tag_bind('handle%d' % i, "<Key-d>",
            #              lambda ev, i=i: self.remove_point_idx(i))
                      
            self.dots[i]=dot

        self.highlight_selected_dots()

    def find_index_near(self,x,y):
        tags = self.gettags(self.find_closest(x, y))
        try:
            handletags = [t for t in tags if t.startswith('handle')]
            return int(handletags[0][6:])
        except IndexError:
            raise ValueError("no point found")
        
    def new_point_at_mouse(self, ev):
        p = self.world_from_screen(ev.x,ev.y)
        x = p[0]
        y = self.curve.eval(x)
        self.add_point((x, y))

    def add_points(self, pts):
        idxs = [self.curve.insert_pt(p) for p in pts]
        self.select_indices(idxs)
        
    def add_point(self, p):
        self.add_points([p])

    def add_marker(self, p):
        self.markers.insert_pt(p)
        
    def remove_point_idx(self, *idxs):
        idxs = list(idxs)
        while idxs:
            i = idxs.pop()

            self.curve.pop_point(i)
            newsel = []
            newidxs = []
            for si in range(len(self.selected_points)):
                sp = self.selected_points[si]
                if sp == i:
                    continue
                if sp > i:
                    sp -= 1
                newsel.append(sp)
            for ii in range(len(idxs)):
                if ii > i:
                    ii -= 1
                newidxs.append(idxs[ii])

            self.select_indices(newsel)
            idxs[:] = newidxs
            
    def highlight_selected_dots(self):
        if not self.redrawsEnabled:
            return

        for i,d in self.dots.items():
            if i in self.selected_points:
                d.set_property('fill_color', 'red')
            else:
                d.set_property('fill_color', 'blue')
        
    def dotpress(self, r1, r2, ev, dotidx):
        self.print_state("dotpress")
        if dotidx not in self.selected_points:
            self.select_indices([dotidx])

        self.last_mouse_world = self.world_from_screen(ev.x, ev.y)
        self.dragging_dots = True

    def select_between(self,start,end):
        if start > end:
            start, end = end, start
        self.select_indices(self.curve.indices_between(start,end))

    def onEnter(self, widget, event):
        self.entered = True

    def onLeave(self, widget, event):
        self.entered = False

    def onMotion(self, widget, event):
        self.lastMouseX = event.x

        if event.state & Gdk.ModifierType.SHIFT_MASK and 1: # and B1
            self.sketch_motion(event)
            return

        self.select_motion(event)
        
        if not self.dragging_dots:
            return
        if not event.state & 256:
            return # not lmb-down

        # this way is accumulating error and also making it harder to
        # undo (e.g. if the user moves far out of the window or
        # presses esc or something). Instead, we should be resetting
        # the points to their start pos plus our total offset.
        cur = self.world_from_screen(event.x, event.y)
        if self.last_mouse_world:
            delta = (cur[0] - self.last_mouse_world[0],
                     cur[1] - self.last_mouse_world[1])
        else:
            delta = 0,0
        self.last_mouse_world = cur

        self.translate_points(delta)
        

    def translate_points(self, delta):
        moved = False
        
        cp = self.curve.points
        updates = []
        for idx in self.selected_points:

            newp = [cp[idx][0] + delta[0], cp[idx][1] + delta[1]]
            
            newp[1] = max(0,min(1,newp[1]))
            
            if idx>0 and newp[0] <= cp[idx-1][0]:
                continue
            if idx<len(cp)-1 and newp[0] >= cp[idx+1][0]:
                continue
            moved = True
            updates.append((idx, tuple(newp)))
        self.curve.set_points(updates)
        return moved
            
    def unselect(self):
        self.select_indices([])

    def onScroll(self, widget, event):
        t = self.world_from_screen(event.x, 0)[0]
        self.zoomControl.zoom_about_mouse(
            t, factor=1.5 if event.direction == Gdk.ScrollDirection.DOWN else 1/1.5)
        # Don't actually scroll the canvas! (it shouldn't have room to
        # scroll anyway, but it does because of some coordinate errors
        # and borders and stuff)
        return True 
        
    def onRelease(self, widget, event):
        self.print_state("dotrelease")

        if event.state & Gdk.ModifierType.SHIFT_MASK: # relese-B1
            self.sketch_release(event)
            return

        self.select_release(event)
 
        if not self.dragging_dots:
            return
        self.last_mouse_world = None
        self.dragging_dots = False

class CurveRow(object):
    """
    one of the repeating curve rows (including widgets on the left)

    i wish these were in a list-style TreeView so i could set_reorderable on it

    please pack self.box
    """
    def __init__(self, graph, name, curve, markers, zoomControl):
        self.graph = graph
        self.name = name
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.box.set_border_width(1)

        self.cols = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.box.add(self.cols)
        
        controls = Gtk.Frame()
        controls.set_size_request(160, -1)
        controls.set_shadow_type(Gtk.ShadowType.OUT)
        self.cols.pack_start(controls, expand=False, fill=True, padding=0)
        self.setupControls(controls, name, curve)

        self.curveView = Curveview(curve, markers,
                                   isMusic=name in ['music', 'smooth_music'],
                                   zoomControl=zoomControl)
        
        self.initCurveView()
        dispatcher.connect(self.rebuild, "all curves rebuild")

    def isFocus(self):
        return self.curveView.widget.is_focus()
        
    def rebuild(self):
        raise NotImplementedError('obsolete, if curves are drawing right')
        self.curveView.rebuild()
        self.initCurveView()
        self.update_ui_to_collapsed_state()

    def destroy(self):
        self.curveView.entered = False  # help suppress bad position events
        del self.curveView
        self.box.destroy()
        
    def initCurveView(self):
        self.curveView.widget.show()
        self.setHeight(100)
        self.cols.pack_start(self.curveView.widget, expand=True, fill=True, padding=0)       

    def setHeight(self, h):
        self.curveView.widget.set_size_request(-1, h)

        # this should have been automatic when the size changed, but
        # the signals for that are wrong somehow.
        reactor.callLater(0, self.curveView.setCanvasToWidgetSize) 
        
    def setupControls(self, controls, name, curve):
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        controls.add(box)

        curve_name_label = Gtk.LinkButton()
        print "need to truncate this name length somehow"
        def update_label():
            # todo: abort if we don't still exist...
            p = curve_name_label.props
            p.uri = curve.uri
            p.label = self.graph.label(curve.uri)
        self.graph.addHandler(update_label)
        

        self.muted = Gtk.CheckButton("M")
        self.muted.connect("toggled", self.sync_mute_to_curve)
        dispatcher.connect(self.mute_changed, 'mute changed', sender=curve)

        box.pack_start(curve_name_label, expand=True, fill=True, padding=0)
        box.pack_start(self.muted, expand=True, fill=True, padding=0)

    def onDelete(self):
        self.curveView.onDelete()
        
    def sync_mute_to_curve(self, *args):
        """send value from CheckButton to the master attribute inside Curve"""
        new_mute = self.muted.get_active()
        self.curveView.curve.muted = new_mute

    def update_mute_look(self):
        """set colors on the widgets in the row according to self.muted.get()"""
        # not yet ported for gtk
        return
        if self.curveView.curve.muted:
            new_bg = 'grey20'
        else:
            new_bg = 'normal'

        for widget in self.widgets:
            widget['bg'] = new_bg

    def mute_changed(self):
        """call this if curve.muted changed"""
        self.muted.set_active(self.curveView.curve.muted)
        #self.update_mute_look()


class Curvesetview(object):
    """
    
    """
    def __init__(self, graph, curvesVBox, zoomControlBox, curveset):
        self.graph = graph
        self.live = True
        self.curvesVBox = curvesVBox
        self.curveset = curveset
        self.allCurveRows = set()
        self.visibleHeight = 1000

        self.zoomControl = self.initZoomControl(zoomControlBox)
        self.zoomControl.redrawzoom()

        for uri, label, curve in curveset.currentCurves():
            self.add_curve(uri, label, curve) 

        dispatcher.connect(self.clear_curves, "clear_curves")
        dispatcher.connect(self.add_curve, "add_curve", sender=self.curveset)
        dispatcher.connect(self.set_featured_curves, "set_featured_curves")
        dispatcher.connect(self.song_has_changed, "song_has_changed")
        
        self.newcurvename = Gtk.EntryBuffer.new("", 0)

        eventBox = self.curvesVBox.get_parent()
        eventBox.connect("key-press-event", self.onKeyPress)
        eventBox.connect("button-press-event", self.takeFocus)

        self.watchCurveAreaHeight()

    def __del__(self):
        print "del curvesetview", id(self) 

    def initZoomControl(self, zoomControlBox):
        import light9.curvecalc.zoomcontrol
        reload(light9.curvecalc.zoomcontrol)
        zoomControl = light9.curvecalc.zoomcontrol.ZoomControl()
        zoomControlBox.add(zoomControl.widget)
        zoomControl.widget.show_all()
        return zoomControl
        
    def clear_curves(self):
        """curveset is about to re-add all new curves"""
        while self.allCurveRows:
            self.allCurveRows.pop().destroy()

    def song_has_changed(self):
        self.zoomControl.redrawzoom()
        
    def takeFocus(self, *args):
        """the whole curveset's eventbox is what gets the focus, currently, so
        keys like 'c' can work in it"""
        dispatcher.send("all curves lose selection")
        self.curvesVBox.get_parent().grab_focus()

    def curveRow_from_name(self, name):
        for cr in self.allCurveRows:
            if cr.name == name:
                return cr
        raise ValueError("couldn't find curveRow named %r" % name)

    def set_featured_curves(self, curveNames):
        """bring these curves to the top of the stack"""
        for n in curveNames[::-1]:
            self.curvesVBox.reorder_child(self.curveRow_from_name(n).box,
                                          Gtk.PACK_START)
        
    def onKeyPress(self, widget, event):
        if not self.live: # workaround for old instances living past reload()
            return

        r = self.row_under_mouse()
        key = event.string
        pass # no handlers right now
 
    def row_under_mouse(self):
        x, y = self.curvesVBox.get_pointer()
        for r in self.allCurveRows:
            inRowX, inRowY = self.curvesVBox.translate_coordinates(r.box, x, y)
            alloc = r.box.get_allocation()
            if 0 <= inRowX < alloc.width and 0 <= inRowY < alloc.height:
                return r
        raise ValueError("no curveRow is under the mouse")

    def focus_entry(self):
        self.entry.focus()

    def new_curve(self, event):
        self.curveset.new_curve(self.newcurvename.get())
        self.newcurvename.set('')
        
    def add_curve(self, uri, label, curve):
        if isinstance(label, Literal):
            label = str(label)

        f = CurveRow(self.graph, label, curve, self.curveset.markers,
                     self.zoomControl)
        self.curvesVBox.pack_start(f.box, expand=True, fill=True, padding=0)
        f.box.show_all()
        self.allCurveRows.add(f)
        self.setRowHeights()
        f.curveView.goLive()

    def watchCurveAreaHeight(self):
        def sizeEvent(w, size):
            # this is firing really often
            if self.visibleHeight == size.height:
                return
            log.debug("size.height is new: %s", size.height)
            self.visibleHeight = size.height
            self.setRowHeights()

        visibleArea = self.curvesVBox.get_parent().get_parent()
        visibleArea.connect('size-allocate', sizeEvent)

        dispatcher.connect(self.setRowHeights, "curve row focus change")
        
    def setRowHeights(self):
        nRows = len(self.allCurveRows)
        if not nRows:
            return
        anyFocus = any(r.isFocus() for r in self.allCurveRows)

        evenHeight = max(14, self.visibleHeight // nRows) - 3
        if anyFocus:
            focusHeight = max(100, evenHeight)
            if nRows > 1:
                otherHeight = max(14,
                                  (self.visibleHeight - focusHeight) //
                                  (nRows - 1)) - 3
        else:
            otherHeight = evenHeight
        for row in self.allCurveRows:
            row.setHeight(focusHeight if row.isFocus() else otherHeight)
            
    def row(self, name):
        if isinstance(name, Literal):
            name = str(name)
        matches = [r for r in self.allCurveRows if r.name == name]
        if not matches:
            raise ValueError("no curveRow named %r. only %s" %
                             (name, [r.name for r in self.allCurveRows]))
        return matches[0]

    def goLive(self):
        """for startup performance, none of the curves redraw
        themselves until this is called once (and then they're normal)"""
        
        for cr in self.allCurveRows:
            cr.curveView.goLive()

    def onDelete(self):
        for r in self.allCurveRows:
            r.onDelete()


        
