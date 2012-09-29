import logging, traceback
from twisted.python.filepath import FilePath
from twisted.internet.inotify import IN_CLOSE_WRITE, IN_MOVED_FROM
from rdflib import Graph
from light9.rdfdb.patch import Patch
from light9.rdfdb.rdflibpatch import inContext

log = logging.getLogger()

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

        notifier.watch(FilePath(path),
                       mask=IN_CLOSE_WRITE | IN_MOVED_FROM,
                       callbacks=[self.notify])
        self.reread()
      
    def notify(self, notifier, filepath, mask):
        log.info("file %s changed" % filepath)
        try:
            self.reread()
        except Exception:
            traceback.print_exc()

    def reread(self):
        """update the graph with any diffs from this file"""
        old = self.getSubgraph(self.uri)
        new = Graph()
        try:
            new.parse(location=self.path, format='n3')
        except SyntaxError as e:
            print e
            log.error("syntax error in %s" % self.path)
            return

        old = inContext(old, self.uri)
        new = inContext(new, self.uri)
        print "old %s new %s" % (old, new)

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
        
