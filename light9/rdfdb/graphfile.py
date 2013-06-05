import logging, traceback, os, time
from twisted.python.filepath import FilePath
from twisted.internet import reactor
from twisted.internet.inotify import humanReadableMask
from rdflib import Graph
from light9.rdfdb.patch import Patch
from light9.rdfdb.rdflibpatch import inContext

log = logging.getLogger('graphfile')
iolog = logging.getLogger('io')

class GraphFile(object):
    """
    one rdf file that we read from, write to, and notice external changes to
    """
    def __init__(self, notifier, path, uri, patch, getSubgraph):
        """
        this does not include an initial reread() call
        """
        self.path, self.uri = path, uri
        self.patch, self.getSubgraph = patch, getSubgraph

        if not os.path.exists(path):
            # can't start notify until file exists
            try:
                os.makedirs(os.path.dirname(path))
            except OSError:
                pass
            f = open(path, "w")
            f.close()
            iolog.info("created %s", path)

        self.flushDelay = 2 # seconds until we have to call flush() when dirty
        self.writeCall = None # or DelayedCall
        self.lastWriteTimestamp = 0 # mtime from the last time _we_ wrote

        # emacs save comes in as IN_MOVE_SELF, maybe
        
        # I was hoping not to watch IN_CHANGED and get lots of
        # half-written files, but emacs doesn't close its files after
        # a write, so there's no other event. I could try to sleep
        # until after all the writes are done, but I think the only
        # bug left is that we'll retry too agressively on a file
        # that's being written

        from twisted.internet.inotify import IN_CLOSE_WRITE, IN_MOVED_FROM, IN_MODIFY, IN_DELETE, IN_DELETE_SELF, IN_CHANGED

        notifier.watch(FilePath(path),
                       mask=IN_CLOSE_WRITE | IN_MOVED_FROM | IN_DELETE | IN_DELETE_SELF | IN_CHANGED | 16383,
                       callbacks=[self.notify])
      
    def notify(self, notifier, filepath, mask):
        # this is from some other version, and I forget the point. Delete
#        mask = humanReadableMask(mask)
#        if mask[0] in ['open', 'access', 'close_nowrite', 'attrib', 'delete_self']:
#            return

        try:
            if filepath.getModificationTime() == self.lastWriteTimestamp:
                log.debug("file %s changed, but we did this write", filepath)
                return
        except OSError as e:
            log.error("watched file %s: %r" % (filepath, e))
            return
            
        log.info("file %s changed", filepath)
        try:
            self.reread()
        except Exception:
            traceback.print_exc()

    def reread(self):
        """update the graph with any diffs from this file

        n3 parser fails on "1.e+0" even though rdflib was emitting that itself
        """
        old = self.getSubgraph(self.uri)
        new = Graph()
        try:
            new.parse(location=self.path, format='n3')
        except SyntaxError as e:
            print e
            traceback.print_exc()
            log.error("syntax error in %s" % self.path)
            return
        except IOError as e:
            log.error("rereading %s: %r" % (self.uri, e))
            return

        old = inContext(old, self.uri)
        new = inContext(new, self.uri)

        p = Patch.fromDiff(old, new)
        if p:
            self.patch(p, dueToFileChange=True)

    def dirty(self, graph):
        """
        there are new contents for our file
        
        graph is the rdflib.Graph that contains the contents of the
        file. It is allowed to change. Note that dirty() will probably
        do the save later when the graph might be different.
        
        after a timer has passed, write it out. Any scheduling issues
        between files? i don't think so. the timer might be kind of
        huge, and then we might want to take a hint from a client that
        it's a good time to save the files that it was editing, like
        when the mouse moves out of the client's window and might be
        going towards a text file editor
        
        """
        log.info("%s dirty, %s stmt" % (self.uri, len(graph)))

        self.graphToWrite = graph
        if self.writeCall:
            self.writeCall.reset(self.flushDelay)
        else:
            self.writeCall = reactor.callLater(self.flushDelay, self.flush)

    def flush(self):
        self.writeCall = None

        tmpOut = self.path + ".rdfdb-temp"
        f = open(tmpOut, 'w')
        t1 = time.time()
        self.graphToWrite.serialize(destination=f, format='n3')
        serializeTime = time.time() - t1
        f.close()
        self.lastWriteTimestamp = os.path.getmtime(tmpOut)
        os.rename(tmpOut, self.path)
        iolog.info("rewrote %s in %.1f ms", self.path, serializeTime * 1000)
        
