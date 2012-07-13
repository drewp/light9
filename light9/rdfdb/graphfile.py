import logging
from twisted.python.filepath import FilePath
from rdflib import Graph
from light9.rdfdb.patch import Patch

log = logging.getLogger()

class GraphFile(object):
    """
    one rdf file that we read from, write to, and notice external changes to
    """
    def __init__(self, notifier, path, uri, patch, getSubgraph):
        self.path, self.uri = path, uri
        self.patch, self.getSubgraph = patch, getSubgraph

        notifier.watch(FilePath(path), callbacks=[self.notify])
        self.reread()
      
    def notify(self, notifier, filepath, mask):
        log.info("file %s changed" % filepath)
        self.reread()

    def reread(self):
        """update the graph with any diffs from this file"""
        old = self.getSubgraph(self.uri)
        new = Graph()
        new.parse(location=self.path, format='n3')

        adds = [(s, p, o, self.uri) for s, p, o in new - old]
        dels = [(s, p, o, self.uri) for s, p, o in old - new]

        if adds or dels:
            self.patch(Patch(addQuads=adds, delQuads=dels))
