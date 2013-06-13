import restkit, time, json, logging
from light9 import networking
from threading import Thread
from restkit.errors import ResourceNotFound
import http_parser.http
log = logging.getLogger()

class MusicTime(object):
    """
    fetch times from ascoltami in a background thread; return times
    upon request, adjusted to be more precise with the system clock
    """
    def __init__(self, period=.2, onChange=lambda position: None):
        """period is the seconds between http time requests.

        We call onChange with the time in seconds and the total time

        The choice of period doesn't need to be tied to framerate,
        it's more the size of the error you can tolerate (since we
        make up times between the samples, and we'll just run off the
        end of a song)
        """
        self.period = period
        self.onChange = onChange
        self.musicResource = restkit.Resource(networking.musicPlayer.url)
        self.curveCalc = restkit.Resource(networking.curveCalc.url)
        t = Thread(target=self._timeUpdate)
        t.setDaemon(True)
        t.start()

    def getLatest(self):
        """
        dict with 't' and 'song', etc.

        Note that this may be called in a gst camera capture thread.
        """
        if not hasattr(self, 'position'):
            return {'t' : 0, 'song' : None}
        pos = self.position.copy()
        if pos['playing']:
            pos['t'] = pos['t'] + (time.time() - self.positionFetchTime)
        else:
            try:
                # todo: this is blocking for a long while if CC is
                # down. Either make a tiny timeout, or go async
                r = self.curveCalc.get("hoverTime")
            except (ResourceNotFound, http_parser.http.NoMoreData, Exception):
                pass
            else:
                pos['hoverTime'] = json.loads(r.body_string())['hoverTime']
        return pos

    def _timeUpdate(self):
        while True:
            try:
                position = json.loads(self.musicResource.get("time").body_string())

                # this is meant to be the time when the server gave me its
                # report, and I don't know if that's closer to the
                # beginning of my request or the end of it (or some
                # fraction of the way through)
                self.positionFetchTime = time.time()

                self.position = position
                self.onChange(position)
            except restkit.RequestError, e:
                log.error(e)
                time.sleep(1)
            time.sleep(self.period)

    def sendTime(self, t):
        """request that the player go to this time"""
        self.musicResource.post("time", payload=json.dumps({"t" : t}),
                                headers={"content-type" : "application/json"})
