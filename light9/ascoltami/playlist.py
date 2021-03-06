from light9.showconfig import songOnDisk
from light9.namespaces import L9


class NoSuchSong(ValueError):
    """Raised when a song is requested that doesn't exist (e.g. one
    after the last song in the playlist)."""


class Playlist(object):

    def __init__(self, graph, playlistUri):
        self.graph = graph
        self.songs = list(graph.items(playlistUri))

    def nextSong(self, currentSong):
        """Returns the next song in the playlist or raises NoSuchSong if 
        we are at the end of the playlist."""
        try:
            currentIndex = self.songs.index(currentSong)
        except IndexError:
            raise ValueError("%r is not in the current playlist (%r)." %
                             (currentSong, self.playlistUri))

        try:
            nextSong = self.songs[currentIndex + 1]
        except IndexError:
            raise NoSuchSong("%r is the last item in the playlist." %
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
