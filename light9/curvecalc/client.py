"""
client code for talking to curvecalc
"""
import cyclone.httpclient
from light9 import networking
import urllib.request, urllib.parse, urllib.error


def sendLiveInputPoint(curve, value):
    f = cyclone.httpclient.fetch(networking.curveCalc.path('liveInputPoint'),
                                 method='POST',
                                 timeout=1,
                                 postdata=urllib.parse.urlencode({
                                     'curve':
                                     curve,
                                     'value':
                                     str(value),
                                 }))

    @f.addCallback
    def cb(result):
        if result.code // 100 != 2:
            raise ValueError("curveCalc said %s: %s", result.code, result.body)

    return f
