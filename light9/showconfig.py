import logging, warnings
from twisted.python.filepath import FilePath
from os import path, getenv
from rdflib import Graph
from rdflib import URIRef
from namespaces import MUS, L9
log = logging.getLogger('showconfig')

_config = None # graph
def getGraph():
    warnings.warn("code that's using showconfig.getGraph should be "
                  "converted to use the sync graph", stacklevel=2)
    global _config
    if _config is None:
        graph = Graph()
        # note that logging is probably not configured the first time
        # we're in here
        print "reading n3 files around %r" % root()
        for f in FilePath(root()).globChildren("*.n3") + FilePath(root()).globChildren("build/*.n3"):
            print "reading %s" % f
            graph.parse(location=f.path, format='n3')
        _config = graph
    return _config

def root():
    r = getenv("LIGHT9_SHOW")
    if r is None:
        raise OSError(
            "LIGHT9_SHOW env variable has not been set to the show root")
    return r

def showUri():
    """Return the show URI associated with $LIGHT9_SHOW."""
    return URIRef(file(path.join(root(), 'URI')).read().strip())

def songOnDisk(song):
    """given a song URI, where's the on-disk file that mpd would read?"""
    graph = getGraph()
    root = graph.value(showUri(), L9['musicRoot'])
    if not root:
        raise ValueError("%s has no :musicRoot" % showUri())

    name = graph.value(song, L9['songFilename'])
    if not name:
        raise ValueError("Song %r has no :songFilename" % song)

    return path.abspath(path.join(root, name))

def songFilenameFromURI(uri):
    """
    'http://light9.bigasterisk.com/show/dance2007/song8' -> 'song8'

    everything that uses this should be deprecated for real URIs
    everywhere"""
    assert isinstance(uri, URIRef)
    return uri.split('/')[-1]

def getSongsFromShow(graph, show):
    playList = graph.value(show, L9['playList'])
    if not playList:
        raise ValueError("%r has no l9:playList" % show)
    songs = [
        # this was graph.items(playlistUri) but i was getting other
        # items from a totally different list! seems like bnode
        # corruption.
        URIRef("http://light9.bigasterisk.com/show/dance2014/song1"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song2"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song3"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song4"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song5"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song6"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song7"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song8"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song9"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song10"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song11"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song12"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song13"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song14"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song15"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song16"),
        URIRef("http://light9.bigasterisk.com/show/dance2014/song17"),
    ]
    # probably fixed with the patch in https://github.com/RDFLib/rdflib/issues/305
    #songs = list(graph.items(playList))

    return songs

def curvesDir():
    return path.join(root(),"curves")

def subFile(subname):
    return path.join(root(),"subs",subname)

def subsDir():
    return path.join(root(),'subs')
