"""
like videorecorder.py, but talks to a bin/picamserve instance
"""
import os, time, logging
import gtk
import numpy
import treq
from twisted.internet import defer
from light9.vidref.replay import framerate, songDir, takeDir, snapshotDir
from light9 import prof, showconfig
from light9.namespaces import L9
from PIL import Image
from StringIO import StringIO
log = logging.getLogger('remotepi')

class Pipeline(object):
    def __init__(self, liveVideo, musicTime, recordingTo, graph):
        self.musicTime = musicTime
        self.recordingTo = recordingTo

        self.liveVideo = self._replaceLiveVideoWidget(liveVideo)
        
        self._snapshotRequests = []
        self.graph = graph
        self.graph.addHandler(self.updateCamUrl)

    def updateCamUrl(self):
        show = showconfig.showUri()
        self.picsUrl = self.graph.value(show, L9['vidrefCamRequest'])
        log.info("picsUrl now %r", self.picsUrl)
        if not self.picsUrl:
            return
        
        # this cannot yet survive being called a second time
        self._startRequest(str(self.picsUrl.replace('/pic', '/pics')) +
                           '&res=1080&resize=450')
        
    def _replaceLiveVideoWidget(self, liveVideo):
        aspectFrame = liveVideo.get_parent()
        liveVideo.destroy()
        img = gtk.Image()
        img.set_visible(True)
        #img.set_size_request(320, 240)
        aspectFrame.add(img)
        return img
        
    def _startRequest(self, url):
        self._buffer = ''
        log.info('start request to %r', url)
        d = treq.get(url)
        d.addCallback(treq.collect, self._dataReceived)
        # not sure how to stop this
        return d

    def _dataReceived(self, chunk):
        self._buffer += chunk
        if len(self._buffer) < 100:
            return
        i = self._buffer.index('\n')
        size, frameTime = self._buffer[:i].split()
        size = int(size)
        if len(self._buffer) - i - 1 < size:
            return
        jpg = self._buffer[i+1:i+1+size]
        self.onFrame(jpg, float(frameTime))
        self._buffer = self._buffer[i+1+size:]
        
    def snapshot(self):
        """
        returns deferred to the path (which is under snapshotDir()) where
        we saved the image.
        """
        filename = "%s/%s.jpg" % (snapshotDir(), time.time())
        d = defer.Deferred()
        self._snapshotRequests.append((d, filename))
        return d

    def setInput(self, name):
        pass

    def setLiveVideo(self, on):
        print "setLiveVideo", on

    def onFrame(self, jpg, frameTime):
        # We could pass frameTime here to try to compensate for lag,
        # but it ended up looking worse in a test. One suspect is the
        # rpi clock drift might be worse than the lag. The value of
        # (now - frameTime) stutters regularly between 40ms, 140ms,
        # and 200ms.
        position = self.musicTime.getLatest()

        for d, filename in self._snapshotRequests:
            with open(filename, 'w') as out:
                out.write(jpg)
            d.callback(filename)
        self._snapshotRequests[:] = []
            
        
        if not position['song']:
            self.updateLiveFromTemp(jpg)
            return 
        outDir = takeDir(songDir(position['song']), position['started'])
        outFilename = "%s/%08.03f.jpg" % (outDir, position['t'])
        if os.path.exists(outFilename): # we're paused on one time
            self.updateLiveFromTemp(jpg)
            return
        try:
            os.makedirs(outDir)
        except OSError:
            pass
        with open(outFilename, 'w') as out:
            out.write(jpg)

        self.updateLiveFromFile(outFilename)
            
        # if you're selecting the text while gtk is updating it,
        # you can get a crash in xcb_io
        if getattr(self, '_lastRecText', None) != outDir:
            with gtk.gdk.lock:
                self.recordingTo.set_text(outDir)
            self._lastRecText = outDir
            
    def updateLiveFromFile(self, outFilename):
        self.liveVideo.set_from_file(outFilename)

    def updateLiveFromTemp(self, jpg):
        try:
            img = Image.open(StringIO(jpg))
            if not hasattr(self, 'livePixBuf'):
                self.livePixBuf = gtk.gdk.pixbuf_new_from_data(
                    img.tobytes(),
                    gtk.gdk.COLORSPACE_RGB,
                    False, 8,
                    img.size[0], img.size[1],
                    img.size[0]*3)
                log.info("live images are %r", img.size)
            else:
                # don't leak pixbufs; update the one we have
                a = self.livePixBuf.pixel_array
                newImg = numpy.fromstring(img.tobytes(), dtype=numpy.uint8)
                a[:,:,:] = newImg.reshape(a.shape)
            self.liveVideo.set_from_pixbuf(self.livePixBuf)

        except Exception:
            import traceback
            traceback.print_exc()
