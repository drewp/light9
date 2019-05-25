"""
this may be split out from curvecalc someday, since it doesn't
need to be tied to a gui """
import cgi
from twisted.internet import reactor
import cyclone.web, cyclone.httpclient, cyclone.websocket
from rdflib import URIRef
from cycloneerr import PrettyErrorHandler
from louie import dispatcher


def serveCurveEdit(port, hoverTimeResponse, curveset):
    """
    /hoverTime requests actually are handled by the curvecalc gui
    """
    curveEdit = CurveEdit(curveset)

    class HoverTime(PrettyErrorHandler, cyclone.web.RequestHandler):

        def get(self):
            hoverTimeResponse(self)

    class LiveInputPoint(PrettyErrorHandler, cyclone.web.RequestHandler):

        def post(self):
            params = cgi.parse_qs(self.request.body)
            curve = URIRef(params['curve'][0])
            value = float(params['value'][0])
            curveEdit.liveInputPoint(curve, value)
            self.set_status(204)

    reactor.listenTCP(
        port,
        cyclone.web.Application(handlers=[
            (r'/hoverTime', HoverTime),
            (r'/liveInputPoint', LiveInputPoint),
        ],
                                debug=True))


class CurveEdit(object):

    def __init__(self, curveset):
        self.curveset = curveset
        dispatcher.connect(self.inputTime, "input time")
        self.currentTime = 0

    def inputTime(self, val):
        self.currentTime = val

    def liveInputPoint(self, curveUri, value):
        curve = self.curveset.curveFromUri(curveUri)
        curve.live_input_point((self.currentTime, value), clear_ahead_secs=.5)
