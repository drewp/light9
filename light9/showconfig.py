import logging, warnings
from twisted.python.filepath import FilePath
from os import path, getenv
from rdflib import Graph
from rdflib import URIRef, Literal
from .namespaces import L9
from typing import List, cast
log = logging.getLogger('showconfig')

_config = None  # graph


def getGraph() -> Graph:
    warnings.warn(
        "code that's using showconfig.getGraph should be "
        "converted to use the sync graph",
        stacklevel=2)
    global _config
    if _config is None:
        graph = Graph()
        # note that logging is probably not configured the first time
        # we're in here
        warnings.warn("reading n3 files around %r" % root())
        for f in FilePath(root()).globChildren("*.n3") + FilePath(
                root()).globChildren("build/*.n3"):
            graph.parse(location=f.path, format='n3')
        _config = graph
    return _config


def root() -> bytes:
    r = getenv("LIGHT9_SHOW")
    if r is None:
        raise OSError(
            "LIGHT9_SHOW env variable has not been set to the show root")
    return r.encode('ascii')


_showUri = None


def showUri() -> URIRef:
    """Return the show URI associated with $LIGHT9_SHOW."""
    global _showUri
    if _showUri is None:
        _showUri = URIRef(open(path.join(root(), b'URI')).read().strip())
    return _showUri


def songOnDisk(song: URIRef) -> bytes:
    """given a song URI, where's the on-disk file that mpd would read?"""
    graph = getGraph()
    root = graph.value(showUri(), L9['musicRoot'])
    if not root:
        raise ValueError("%s has no :musicRoot" % showUri())

    name = graph.value(song, L9['songFilename'])
    if not name:
        raise ValueError("Song %r has no :songFilename" % song)

    return path.abspath(
        path.join(
            cast(Literal, root).toPython(),
            cast(Literal, name).toPython()))


def songFilenameFromURI(uri: URIRef) -> bytes:
    """
    'http://light9.bigasterisk.com/show/dance2007/song8' -> 'song8'

    everything that uses this should be deprecated for real URIs
    everywhere"""
    assert isinstance(uri, URIRef)
    return str(uri).split('/')[-1].encode('ascii')


def getSongsFromShow(graph: Graph, show: URIRef) -> List[URIRef]:
    playList = graph.value(show, L9['playList'])
    if not playList:
        raise ValueError("%r has no l9:playList" % show)
    # The patch in https://github.com/RDFLib/rdflib/issues/305 fixed a
    # serious bug here.
    songs = list(graph.items(playList))

    return songs


def curvesDir():
    return path.join(root(), b"curves")


def subFile(subname):
    return path.join(root(), b"subs", subname)


def subsDir():
    return path.join(root(), b'subs')
