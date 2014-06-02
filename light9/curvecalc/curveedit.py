"""
this may be split out from curvecalc someday, since it doesn't
need to be tied to a gui """
from twisted.internet import reactor
import cyclone.web, cyclone.httpclient, cyclone.websocket

from lib.cycloneerr import PrettyErrorHandler


def serveCurveEdit(port, hoverTimeResponse):
    """
    /hoverTime requests actually are handled by the curvecalc gui
    """

    class HoverTime(PrettyErrorHandler, cyclone.web.RequestHandler):
        def get(self):
            hoverTimeResponse(self)

    reactor.listenTCP(port, cyclone.web.Application(handlers=[
        (r'/hoverTime', HoverTime),
        ], debug=True))
