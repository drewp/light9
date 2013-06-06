import time, logging, warnings
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
        for f in FilePath(root()).globChildren("*.n3") + FilePath(root()).globChildren("build/*.n3"):
            log.info("reading %s", f)
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

def findMpdHome():
    """top of the music directory for the mpd on this system,
    including trailing slash"""
    
    mpdHome = None
    for mpdConfFilename in ["/my/dl/modified/mpd/src/mpdconf-testing",
                            "~/.mpdconf", "/etc/mpd.conf"]:
        try:
            mpdConfFile = open(path.expanduser(mpdConfFilename))
        except IOError:
            continue
        for line in mpdConfFile:
            if line.startswith("music_directory"):
                mpdHome = line.split()[1].strip('"')
                return mpdHome.rstrip(path.sep) + path.sep  

    raise ValueError("can't find music_directory in any mpd config file")

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
    songs = list(graph.items(playList))

    return songs

def curvesDir():
    return path.join(root(),"curves")

def songFilename(song):
    return path.join(root(), "music", "%s.wav" % song)

def subtermsForSong(song):
    return path.join(root(),"subterms",song)

def subFile(subname):
    return path.join(root(),"subs",subname)

def subsDir():
    return path.join(root(),'subs')

def prePostSong():
    graph = getGraph()
    return [graph.value(MUS['preSong'], L9['showPath']),
            graph.value(MUS['postSong'], L9['showPath'])]
