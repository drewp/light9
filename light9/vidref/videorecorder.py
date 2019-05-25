import pygst
pygst.require("0.10")
import gst, gobject, time, logging, os, traceback
import gtk
from PIL import Image
from threading import Thread
from twisted.internet import defer
from queue import Queue, Empty
from light9.vidref.replay import framerate, songDir, takeDir, snapshotDir
log = logging.getLogger()


class Pipeline(object):

    def __init__(self, liveVideoXid, musicTime, recordingTo):
        self.musicTime = musicTime
        self.liveVideoXid = liveVideoXid
        self.recordingTo = recordingTo
        self.snapshotRequests = Queue()

        try:
            os.makedirs(snapshotDir())
        except OSError:
            pass

    def snapshot(self):
        """
        returns deferred to the path (which is under snapshotDir()) where
        we saved the image. This callback comes from another thread,
        but I haven't noticed that being a problem yet.
        """
        d = defer.Deferred()

        def req(frame):
            filename = "%s/%s.jpg" % (snapshotDir(), time.time())
            log.debug("received snapshot; saving in %s", filename)
            frame.save(filename)
            d.callback(filename)

        log.debug("requesting snapshot")
        self.snapshotRequests.put(req)
        return d

    def setInput(self, name):
        sourcePipe = {
            "auto": "autovideosrc name=src1",
            "testpattern": "videotestsrc name=src1",
            "dv": "dv1394src name=src1 ! dvdemux ! dvdec",
            "v4l": "v4l2src device=/dev/video0 name=src1",
        }[name]

        cam = (
            sourcePipe + " ! "
            "videorate ! video/x-raw-yuv,framerate=%s/1 ! "
            "videoscale ! video/x-raw-yuv,width=640,height=480;video/x-raw-rgb,width=320,height=240 ! "
            "videocrop left=160 top=180 right=120 bottom=80 ! "
            "queue name=vid" % framerate)

        print(cam)
        self.pipeline = gst.parse_launch(cam)

        def makeElem(t, n=None):
            e = gst.element_factory_make(t, n)
            self.pipeline.add(e)
            return e

        sink = makeElem("xvimagesink")

        def setRec(t):
            # if you're selecting the text while gtk is updating it,
            # you can get a crash in xcb_io
            if getattr(self, '_lastRecText', None) == t:
                return
            with gtk.gdk.lock:
                self.recordingTo.set_text(t)
            self._lastRecText = t

        recSink = VideoRecordSink(self.musicTime, setRec, self.snapshotRequests)
        self.pipeline.add(recSink)

        tee = makeElem("tee")

        caps = makeElem("capsfilter")
        caps.set_property('caps', gst.caps_from_string('video/x-raw-rgb'))

        gst.element_link_many(self.pipeline.get_by_name("vid"), tee, sink)
        gst.element_link_many(tee, makeElem("ffmpegcolorspace"), caps, recSink)
        sink.set_xwindow_id(self.liveVideoXid)
        self.pipeline.set_state(gst.STATE_PLAYING)

    def setLiveVideo(self, on):

        if on:
            self.pipeline.set_state(gst.STATE_PLAYING)
            # this is an attempt to bring the dv1394 source back, but
            # it doesn't work right.
            self.pipeline.get_by_name("src1").seek_simple(
                gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, 0 * gst.SECOND)
        else:
            self.pipeline.set_state(gst.STATE_READY)


class VideoRecordSink(gst.Element):
    _sinkpadtemplate = gst.PadTemplate("sinkpadtemplate", gst.PAD_SINK,
                                       gst.PAD_ALWAYS, gst.caps_new_any())

    def __init__(self, musicTime, updateRecordingTo, snapshotRequests):
        gst.Element.__init__(self)
        self.updateRecordingTo = updateRecordingTo
        self.snapshotRequests = snapshotRequests
        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.add_pad(self.sinkpad)
        self.sinkpad.set_chain_function(self.chainfunc)
        self.lastTime = 0

        self.musicTime = musicTime

        self.imagesToSave = Queue()
        self.startBackgroundImageSaver(self.imagesToSave)

    def startBackgroundImageSaver(self, imagesToSave):
        """do image saves in another thread to not block gst"""

        def imageSaver():
            while True:
                args = imagesToSave.get()
                self.saveImg(*args)
                imagesToSave.task_done()

                # this is not an ideal place for snapshotRequests
                # since imagesToSave is allowed to get backed up with
                # image writes, yet we would still want the next new
                # image to be used for the snapshot. chainfunc should
                # put snapshot images in a separate-but-similar queue
                # to imagesToSave, and then another watcher could use
                # those to satisfy snapshot requests
                try:
                    req = self.snapshotRequests.get(block=False)
                except Empty:
                    pass
                else:
                    req(args[1])
                    self.snapshotRequests.task_done()

        t = Thread(target=imageSaver)
        t.setDaemon(True)
        t.start()

    def chainfunc(self, pad, buffer):
        position = self.musicTime.getLatest()

        # if music is not playing and there's no pending snapshot
        # request, we could skip the image conversions here.

        try:
            cap = buffer.caps[0]
            #print "cap", (cap['width'], cap['height'])
            img = Image.fromstring('RGB', (cap['width'], cap['height']),
                                   buffer.data)
            self.imagesToSave.put((position, img, buffer.timestamp))
        except Exception:
            traceback.print_exc()

        return gst.FLOW_OK

    def saveImg(self, position, img, bufferTimestamp):
        if not position['song']:
            return

        t1 = time.time()
        outDir = takeDir(songDir(position['song']), position['started'])
        outFilename = "%s/%08.03f.jpg" % (outDir, position['t'])
        if os.path.exists(outFilename):  # we're paused on one time
            return

        try:
            os.makedirs(outDir)
        except OSError:
            pass

        img.save(outFilename)

        now = time.time()
        log.info("wrote %s delay of %.2fms, took %.2fms", outFilename,
                 (now - self.lastTime) * 1000, (now - t1) * 1000)
        self.updateRecordingTo(outDir)
        self.lastTime = now


gobject.type_register(VideoRecordSink)
