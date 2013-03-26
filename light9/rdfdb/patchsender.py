import logging
import cyclone.httpclient
from twisted.internet import defer
log = logging.getLogger('syncedgraph')

class PatchSender(object):
    """
    SyncedGraph may generate patches faster than we can send
    them. This object buffers and may even collapse patches before
    they go the server
    """
    def __init__(self, target, myUpdateResource):
        """
        target is the URI we'll send patches to

        myUpdateResource is the URI for this sender of patches, which
        maybe needs to be the actual requestable update URI for
        sending updates back to us
        """
        self.target = target
        self.myUpdateResource = myUpdateResource
        self._patchesToSend = []
        self._currentSendPatchRequest = None

    def sendPatch(self, p):
        sendResult = defer.Deferred()
        self._patchesToSend.append((p, sendResult))
        self._continueSending()
        return sendResult

    def _continueSending(self):
        if not self._patchesToSend or self._currentSendPatchRequest:
            return
        if len(self._patchesToSend) > 1:
            log.info("%s patches left to send", len(self._patchesToSend))
            # this is where we could concatenate little patches into a
            # bigger one. Often, many statements will cancel each
            # other out. not working yet:
            if 0:
                p = self._patchesToSend[0].concat(self._patchesToSend[1:])
                print "concat down to"
                print 'dels'
                for q in p.delQuads: print q
                print 'adds'
                for q in p.addQuads: print q
                print "----"
            else:
                p, sendResult = self._patchesToSend.pop(0)
        else:
            p, sendResult = self._patchesToSend.pop(0)

        self._currentSendPatchRequest = sendPatch(
            self.target, p, senderUpdateUri=self.myUpdateResource)
        self._currentSendPatchRequest.addCallbacks(self._sendPatchDone,
                                                   self._sendPatchErr)
        self._currentSendPatchRequest.chainDeferred(sendResult)

    def _sendPatchDone(self, result):
        self._currentSendPatchRequest = None
        self._continueSending()

    def _sendPatchErr(self, e):
        self._currentSendPatchRequest = None
        # we're probably out of sync with the master now, since
        # SyncedGraph.patch optimistically applied the patch to our
        # local graph already. What happens to this patch? What
        # happens to further pending patches? Some of the further
        # patches, especially, may be commutable with the bad one and
        # might still make sense to apply to the master graph.

        # if someday we are folding pending patches together, this
        # would be the time to UNDO that and attempt the original
        # separate patches again

        # this should screen for 409 conflict responses and raise a
        # special exception for that, so SyncedGraph.sendFailed can
        # screen for only that type

        # this code is going away; we're going to raise an exception that contains all the pending patches
        log.error("_sendPatchErr")
        log.error(e)
        self._continueSending()

def sendPatch(putUri, patch, **kw):
    """
    PUT a patch as json to an http server. Returns deferred.
    
    kwargs will become extra attributes in the toplevel json object
    """
    body = patch.makeJsonRepr(kw)
    log.debug("send body: %r", body)
    def ok(done):
        if not str(done.code).startswith('2'):
            raise ValueError("sendPatch request failed %s: %s" % (done.code, done.body))
        log.debug("sendPatch finished, response: %s" % done.body)
        return done

    return cyclone.httpclient.fetch(
        url=putUri,
        method='PUT',
        headers={'Content-Type': ['application/json']},
        postdata=body,
        ).addCallback(ok)
