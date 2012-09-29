import logging, traceback
from twisted.python.filepath import FilePath
from twisted.internet.inotify import IN_CLOSE_WRITE, IN_MOVED_FROM
from rdflib import Graph
from light9.rdfdb.patch import Patch

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

        adds = [(s, p, o, self.uri) for s, p, o in new - old]
        dels = [(s, p, o, self.uri) for s, p, o in old - new]

        print "file dels"
        for s  in dels:
            print s
        print "file adds"
        for s in adds:
            print s
        print ""

        
        if adds or dels:
            self.patch(Patch(addQuads=adds, delQuads=dels))
