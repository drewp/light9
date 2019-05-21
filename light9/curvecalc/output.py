import time, logging
from twisted.internet import reactor
from light9 import Submaster, dmxclient
from light9.namespaces import L9
from light9.curvecalc.subterm import Subterm

from louie import dispatcher
log = logging.getLogger("output")


class Output(object):
    lastsendtime = 0
    lastsendlevs = None

    def __init__(self, graph, session, music, curveset, currentSubterms):
        self.graph, self.session, self.music = graph, session, music
        self.currentSubterms = currentSubterms
        self.curveset = curveset

        self.recent_t = []
        self.later = None

        self.update()

    def update(self):
        d = self.music.current_time()
        d.addCallback(self.update2)
        d.addErrback(self.updateerr)

    def updateerr(self, e):

        print e.getTraceback()
        dispatcher.send("update status", val=e.getErrorMessage())
        if self.later and not self.later.cancelled and not self.later.called:
            self.later.cancel()
        self.later = reactor.callLater(1, self.update)

    def update2(self, t):
        # spot alsa soundcard offset is always 0, we get times about a
        # second ahead of what's really getting played
        #t = t - .7
        dispatcher.send("update status",
                        val="ok: receiving time from music player")
        if self.later and not self.later.cancelled and not self.later.called:
            self.later.cancel()

        self.later = reactor.callLater(.02, self.update)

        self.recent_t = self.recent_t[-50:] + [t]
        period = (self.recent_t[-1] - self.recent_t[0]) / len(self.recent_t)
        dispatcher.send("update period", val=period)
        self.send_dmx(t)

    def send_dmx(self, t):
        dispatcher.send("curves to sliders", t=t)

        if not self.currentSubterms:
            return

        scaledsubs = []
        for st in self.currentSubterms:
            scl = st.scaled(t)
            scaledsubs.append(scl)

        out = Submaster.sub_maxes(*scaledsubs)
        levs = out.get_levels()
        now = time.time()
        if now - self.lastsendtime > 5 or levs != self.lastsendlevs:
            dispatcher.send("output levels", val=levs)
            dmxclient.outputlevels(out.get_dmx_list(),
                                   twisted=1,
                                   clientid='curvecalc')
            self.lastsendtime = now
            self.lastsendlevs = levs
