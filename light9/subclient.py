from light9.collector.collector_client import sendToCollector
from twisted.internet import reactor
from twisted.internet.defer import Deferred
import traceback
import time
import logging
from rdflib import URIRef
from rdfdb.syncedgraph import SyncedGraph
log = logging.getLogger()


class SubClient:
    graph: SyncedGraph
    session: URIRef

    def __init__(self):
        """assumed that your init saves self.graph"""
        pass  # we may later need init code for network setup

    def get_levels_as_sub(self):
        """Subclasses must implement this method and return a Submaster
        object."""

    def send_levels(self):
        self._send_sub()

    def send_levels_loop(self, delay=1000) -> None:
        now = time.time()

        def done(sec):
            reactor.callLater(max(0,
                                  time.time() - (now + delay)),
                              self.send_levels_loop)

        def err(e):
            log.warn('subclient loop: %r', e)
            reactor.callLater(2, self.send_levels_loop)

        d = self._send_sub()
        d.addCallbacks(done, err)

    def _send_sub(self) -> Deferred:
        try:
            with self.graph.currentState() as g:
                outputSettings = self.get_output_settings(_graph=g)
        except Exception:
            traceback.print_exc()
            raise

        return sendToCollector(
            'subclient',
            self.session,
            outputSettings,
            # when KC uses zmq, we get message
            # pileups and delays on collector (even
            # at 20fps). When sequencer uses zmp,
            # it runs great at 40fps. Not sure the
            # difference- maybe Tk main loop?
            useZmq=False)
