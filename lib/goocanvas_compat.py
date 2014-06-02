from gi.repository import GooCanvas

def Points(pts):
    cp = GooCanvas.CanvasPoints.new(len(pts))
    for i, (x, y) in enumerate(pts):
        cp.set_point(i, x, y)
    return cp

def polyline_new_line(parent, x0=None, y0=None, x1=None, y1=None, points=None, **props):
    p = GooCanvas.CanvasPolyline()
    p.set_property('parent', parent)
    if x0 is not None or points is not None:
        pts = points or Points([(x0, y0), (x1, y1)])
        p.set_property('points', pts)
    for k, v in props.items():
        p.set_property(k, v)
    return p
