"""
this may be split out from curvecalc someday, since it doesn't
need to be tied to a gui """
from twisted.internet import reactor
from light9 import networking

def serveCurveEdit(port, hoverTimeResponse):
    """
    /hoverTime requests actually are handled by the curvecalc gui
    """
                       
    from twisted.web import server, resource
    class Hover(resource.Resource):
        isLeaf = True
        def render_GET(self, request):
            if request.path == '/hoverTime':
                return hoverTimeResponse(request)
            raise NotImplementedError()

    reactor.listenTCP(port, server.Site(Hover()))
