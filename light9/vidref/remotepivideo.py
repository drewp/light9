"""
like videorecorder.py, but talks to a bin/picamserve instance
"""
import os, time, logging
import gtk
import numpy
import treq
from light9.vidref.replay import framerate, songDir, takeDir, snapshotDir
from light9 import prof
from PIL import Image
from StringIO import StringIO
log = logging.getLogger('remotepi')

class Pipeline(object):
    def __init__(self, liveVideo, musicTime, recordingTo, picsUrl):
        self.musicTime = musicTime
        self.recordingTo = recordingTo

        self.liveVideo = self._replaceLiveVideoWidget(liveVideo)
        
        self._startRequest(picsUrl)
        self._buffer = ''

    def _replaceLiveVideoWidget(self, liveVideo):
        aspectFrame = liveVideo.get_parent()
        liveVideo.destroy()
        img = gtk.Image()
        img.set_visible(True)
        #img.set_size_request(320, 240)
        aspectFrame.add(img)
        return img
        
    def _startRequest(self, url):
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
        return

    def setInput(self, name):
        pass

    def setLiveVideo(self, on):
        print "setLiveVideo", on

    def onFrame(self, jpg, frameTime):
        position = self.musicTime.getLatest()
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
                    img.tostring(),
                    gtk.gdk.COLORSPACE_RGB,
                    False, 8,
                    img.size[0], img.size[1],
                    img.size[0]*3)
                log.info("live images are %r", img.size)
            else:
                # don't leak pixbufs; update the one we have
                a = self.livePixBuf.pixel_array
                newImg = numpy.fromstring(img.tostring(), dtype=numpy.uint8)
                a[:,:,:] = newImg.reshape(a.shape)
            self.liveVideo.set_from_pixbuf(self.livePixBuf)

        except Exception:
            import traceback
            traceback.print_exc()
