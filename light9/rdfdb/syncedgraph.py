"""
client code uses a SyncedGraph, which has a few things:

AutoDepGraphApi - knockoutjs-inspired API for querying the graph in a
way that lets me call you again when there were changes to the things
you queried

CurrentStateGraphApi - a way to query the graph that doesn't gather
your dependencies like AutoDepGraphApi does

GraphEditApi - methods to write patches to the graph for common
operations, e.g. replacing a value, or editing a mapping

PatchReceiver - our web server that listens to edits from the master graph

PatchSender - collects and transmits your graph edits
"""

from rdflib import ConjunctiveGraph
import logging, cyclone.httpclient, traceback
from twisted.internet import defer
import treq, json
log = logging.getLogger('syncedgraph')
from light9.rdfdb.rdflibpatch import patchQuads

from light9.rdfdb.patchsender import PatchSender
from light9.rdfdb.patchreceiver import PatchReceiver
from light9.rdfdb.currentstategraphapi import CurrentStateGraphApi
from light9.rdfdb.autodepgraphapi import AutoDepGraphApi
from light9.rdfdb.grapheditapi import GraphEditApi

# everybody who writes literals needs to get this
from rdflibpatch_literal import patch
patch()


class SyncedGraph(CurrentStateGraphApi, AutoDepGraphApi, GraphEditApi):
    """
    graph for clients to use. Changes are synced with the master graph
    in the rdfdb process.

    This api is like rdflib.Graph but it can also call you back when
    there are graph changes to the parts you previously read.

    You may want to attach to self.initiallySynced deferred so you
    don't attempt patches before we've heard the initial contents of
    the graph. It would be ok to accumulate some patches of new
    material, but usually you won't correctly remove the existing
    statements unless we have the correct graph.

    If we get out of sync, we abandon our local graph (even any
    pending local changes) and get the data again from the
    server.
    """
    def __init__(self, rdfdbRoot, label):
        """
        label is a string that the server will display in association
        with your connection
        """
        self.rdfdbRoot = rdfdbRoot
        self.initiallySynced = defer.Deferred()
        self._graph = ConjunctiveGraph()

        self._receiver = PatchReceiver(self.rdfdbRoot, label, self._onPatch)
        
        self._sender = PatchSender(self.rdfdbRoot + 'patches',
                                   self._receiver.updateResource)
        AutoDepGraphApi.__init__(self)
        # this needs more state to track if we're doing a resync (and
        # everything has to error or wait) or if we're live
        
    def resync(self):
        """
        get the whole graph again from the server (e.g. we had a
        conflict while applying a patch and want to return to the
        truth).

        To avoid too much churn, we remember our old graph and diff it
        against the replacement. This way, our callers only see the
        corrections.

        Edits you make during a resync will surely be lost, so I
        should just fail them. There should be a notification back to
        UIs who want to show that we're doing a resync.
        """
        log.info('resync')
        self._sender.cancelAll()
        # this should be locked so only one resync goes on at once
        return cyclone.httpclient.fetch(
            url=self.rdfdbRoot + "graph",
            method="GET",
            headers={'Accept':['x-trig']},
            ).addCallback(self._resyncGraph)

    def _resyncGraph(self, response):
        log.warn("new graph in")
        
        #diff against old entire graph
        #broadcast that change

    def patch(self, p):
        """send this patch to the server and apply it to our local
        graph and run handlers"""

        if p.isNoop():
            log.info("skipping no-op patch")
            return
        
        # these could fail if we're out of sync. One approach:
        # Rerequest the full state from the server, try the patch
        # again after that, then give up.
        debugKey = '[id=%s]' % (id(p) % 1000)
        log.debug("\napply local patch %s %s", debugKey, p)
        try:
            patchQuads(self._graph,
                       deleteQuads=p.delQuads,
                       addQuads=p.addQuads,
                       perfect=True)
        except ValueError as e:
            log.error(e)
            self.sendFailed(None)
            return
        log.debug('runDepsOnNewPatch')
        self.runDepsOnNewPatch(p)
        log.debug('sendPatch')
        self._sender.sendPatch(p).addErrback(self.sendFailed)
        log.debug('patch is done %s', debugKey)

    def suggestPrefixes(self, ctx, prefixes):
        """
        when writing files for this ctx, try to use these n3
        prefixes. async, not guaranteed to finish before any
        particular file flush
        """
        treq.post(self.rdfdbRoot + 'prefixes', json.dumps({'ctx': ctx, 'prefixes': prefixes}))

    def sendFailed(self, result):
        """
        we asked for a patch to be queued and sent to the master, and
        that ultimately failed because of a conflict
        """
        log.warn("sendFailed")
        self.resync()
        
        #i think we should receive back all the pending patches,
        #do a resync here,
        #then requeue all the pending patches (minus the failing one?) after that's done.

    def _onPatch(self, p):
        """
        central server has sent us a patch
        """
        log.debug('_onPatch server has sent us %s', p)
        patchQuads(self._graph, p.delQuads, p.addQuads, perfect=True)
        log.debug("graph now has %s statements" % len(self._graph))
        try:
            self.runDepsOnNewPatch(p)
        except Exception:
            # don't reflect this error back to the server; we did
            # receive its patch correctly. However, we're in a bad
            # state since some dependencies may not have rerun
            traceback.print_exc()
            log.warn("some graph dependencies may not have completely run")

        if self.initiallySynced:
            self.initiallySynced.callback(None)
            self.initiallySynced = None
