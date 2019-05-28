import time, json, logging
from typing import Dict

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
import treq

from light9 import networking

log = logging.getLogger()


class MusicTime(object):
    """
    fetch times from ascoltami in a background thread; return times
    upon request, adjusted to be more precise with the system clock
    """

    def __init__(self,
                 period=.2,
                 onChange=lambda position: None,
                 pollCurvecalc=True):
        """period is the seconds between http time requests.

        We call onChange with the time in seconds and the total time

        The choice of period doesn't need to be tied to framerate,
        it's more the size of the error you can tolerate (since we
        make up times between the samples, and we'll just run off the
        end of a song)
        """
        self.period = period
        self.hoverPeriod = .05
        self.onChange = onChange

        self.position: Dict[str, float] = {}
        # driven by our pollCurvecalcTime and also by Gui.incomingTime
        self.lastHoverTime = None  # None means "no recent value"
        self.pollMusicTime()
        if pollCurvecalc:
            self.pollCurvecalcTime()

    def getLatest(self, frameTime=None):
        """
        dict with 't' and 'song', etc.

        frameTime is the timestamp from the camera, which will be used
        instead of now.

        Note that this may be called in a gst camera capture thread. Very often.
        """
        if not hasattr(self, 'position'):
            return {'t': 0, 'song': None}
        pos = self.position.copy()
        now = frameTime or time.time()
        if pos.get('playing'):
            pos['t'] = pos['t'] + (now - self.positionFetchTime)
        else:
            if self.lastHoverTime is not None:
                pos['hoverTime'] = self.lastHoverTime
        return pos

    def pollMusicTime(self):

        @inlineCallbacks
        def cb(response):

            if response.code != 200:
                raise ValueError("%s %s", response.code, (yield response.content()))

            position = yield response.json()

            # this is meant to be the time when the server gave me its
            # report, and I don't know if that's closer to the
            # beginning of my request or the end of it (or some
            # fraction of the way through)
            self.positionFetchTime = time.time()

            self.position = position
            self.onChange(position)

            reactor.callLater(self.period, self.pollMusicTime)

        def eb(err):
            log.warn("talking to ascoltami: %s", err.getErrorMessage())
            reactor.callLater(2, self.pollMusicTime)

        d = treq.get(networking.musicPlayer.path("time").toPython())
        d.addCallback(cb)
        d.addErrback(eb)  # note this includes errors in cb()

    def pollCurvecalcTime(self):
        """
        poll the curvecalc position when music isn't playing, so replay
        can track it.

        This would be better done via rdfdb sync, where changes to the
        curvecalc position are written to the curvecalc session and we
        can pick them up in here
        """
        if self.position.get('playing'):
            # don't need this position during playback
            self.lastHoverTime = None
            reactor.callLater(.2, self.pollCurvecalcTime)
            return

        def cb(response):
            if response.code == 404:
                # not hovering
                self.lastHoverTime = None
                reactor.callLater(.2, self.pollCurvecalcTime)
                return
            if response.code != 200:
                raise ValueError("%s %s" % (response.code, response.body))
            self.lastHoverTime = json.loads(response.body)['hoverTime']

            reactor.callLater(self.hoverPeriod, self.pollCurvecalcTime)

        def eb(err):
            if self.lastHoverTime:
                log.warn("talking to curveCalc: %s", err.getErrorMessage())
            self.lastHoverTime = None
            reactor.callLater(2, self.pollCurvecalcTime)

        d = treq.get(networking.curveCalc.path("hoverTime"))
        d.addCallback(cb)
        d.addErrback(eb)  # note this includes errors in cb()

    def sendTime(self, t):
        """request that the player go to this time"""
        treq.post(
            networking.musicPlayer.path('time'),
            data=json.dumps({
                "t": time
            }).encode('utf8'),
            headers={b"content-type": [b"application/json"]},
        )
