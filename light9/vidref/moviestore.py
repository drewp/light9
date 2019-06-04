import os
from bisect import bisect_left
from rdflib import URIRef
import sys
sys.path.append(
    '/home/drewp/Downloads/moviepy/lib/python2.7/site-packages')  # for moviepy
from moviepy.video.io.ffmpeg_writer import FFMPEG_VideoWriter
from moviepy.video.io.ffmpeg_reader import FFMPEG_VideoReader


class _ResourceDir(object):
    """the disk files for a resource"""

    def __init__(self, root, uri):
        self.root, self.uri = root, uri
        u = self.uri.replace('http://', '').replace('/', '_')
        self.topDir = os.path.join(self.root, u)
        try:
            os.makedirs(self.topDir)
        except OSError:
            pass

    def videoPath(self):
        return os.path.join(self.topDir, 'video.avi')

    def indexPath(self):
        return os.path.join(self.topDir, 'frame_times')


class Writer(object):
    """saves a video of a resource, receiving a frame at a time. Frame timing does not have to be regular."""

    def __init__(self, root, uri):
        self.rd = _ResourceDir(root, uri)
        self.ffmpegWriter = None  # lazy since we don't know the size yet
        self.index = open(self.rd.indexPath(), 'w')
        self.framesWritten = 0

    def save(self, t, img):
        if self.ffmpegWriter is None:
            self.ffmpegWriter = FFMPEG_VideoWriter(
                filename=self.rd.videoPath(),
                size=img.size,
                fps=10,  # doesn't matter, just for debugging playbacks
                codec='libx264')
        self.ffmpegWriter.write_frame(img)
        self.framesWritten = self.framesWritten + 1
        self.index.write('%d %g\n' % (self.framesWritten, t))

    def close(self):
        if self.ffmpegWriter is not None:
            self.ffmpegWriter.close()
        self.index.close()


class Reader(object):

    def __init__(self, resourceDir):
        self.timeFrame = []
        for line in open(resourceDir.indexPath()):
            f, t = line.strip().split()
            self.timeFrame.append((float(t), int(f)))
        self._reader = FFMPEG_VideoReader(resourceDir.videoPath())

    def getFrame(self, t):
        i = bisect_left(self.timeFrame, (t, None))
        i = min(i, len(self.timeFrame) - 1)
        f = self.timeFrame[i][1]
        return self._reader.get_frame(f)


class MultiReader(object):
    """loads the nearest existing frame of a resource's video. Supports random access of multiple resources."""

    def __init__(self, root):
        self.root = root
        # these should cleanup when they haven't been used in a while
        self.readers = {}  # uri: Reader

    def getFrame(self, uri, t):
        if uri not in self.readers:
            #self.readers.close all and pop them
            self.readers[uri] = Reader(_ResourceDir(self.root, uri))
        return self.readers[uri].getFrame(t)


if __name__ == '__main__':
    from PIL import Image
    take = URIRef(
        'http://light9.bigasterisk.com/show/dance2015/song10/1434249076/')
    if 0:
        w = Writer('/tmp/ms', take)
        for fn in sorted(
                os.listdir(
                    '/home/drewp/light9-vidref/play-light9.bigasterisk.com_show_dance2015_song10/1434249076'
                )):
            t = float(fn.replace('.jpg', ''))
            jpg = Image.open(
                '/home/drewp/light9-vidref/play-light9.bigasterisk.com_show_dance2015_song10/1434249076/%08.03f.jpg'
                % t)
            jpg = jpg.resize((450, 176))
            w.save(t, jpg)
        w.close()
    else:
        r = MultiReader('/tmp/ms')
        print((r.getFrame(take, 5.6)))
