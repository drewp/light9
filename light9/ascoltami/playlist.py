from light9.showconfig import getSongsFromShow, songOnDisk
from light9.namespaces import L9
from rdflib import URIRef

class NoSuchSong(ValueError):
    """Raised when a song is requested that doesn't exist (e.g. one
    after the last song in the playlist)."""

class Playlist(object):
    def __init__(self, graph, playlistUri):
        self.graph = graph

        # this should be fixed to share with getSongsFromShow. See note in that one for why I had to stop using graph.items
        self.songs = [
            URIRef("http://light9.bigasterisk.com/show/dance2013/song1"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song2"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song3"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song4"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song5"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song6"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song7"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song8"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song9"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song10"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song11"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song12"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song13"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song14"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song15"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song16"),
            URIRef("http://light9.bigasterisk.com/show/dance2013/song17"),
        ]
        
    def nextSong(self, currentSong):
        """Returns the next song in the playlist or raises NoSuchSong if 
        we are at the end of the playlist."""
        try:
            currentIndex = self.songs.index(currentSong)
        except IndexError:
            raise ValueError("%r is not in the current playlist (%r)." % \
                (currentSong, self.playlistUri))

        try:
            nextSong = self.songs[currentIndex + 1]
        except IndexError:
            raise NoSuchSong("%r is the last item in the playlist." % \
                             currentSong)

        return nextSong

    def allSongs(self):
        """Returns a list of all song URIs in order."""
        return self.songs
    
    def allSongPaths(self):
        """Returns a list of the filesystem paths to all songs in order."""
        paths = []
        for song in self.songs:
            paths.append(songOnDisk(song))
        return paths
    
    def songPath(self, uri):
        """filesystem path to a song"""
        raise NotImplementedError("see showconfig.songOnDisk")
        # maybe that function should be moved to this method

    @classmethod
    def fromShow(playlistClass, graph, show):
        playlistUri = graph.value(show, L9['playList'])
        if not playlistUri:
            raise ValueError("%r has no l9:playList" % show)
        return playlistClass(graph, playlistUri)
