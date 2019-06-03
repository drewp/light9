import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst
from rx.subjects import BehaviorSubject

import time, logging, os, traceback
from PIL import Image
from twisted.internet import defer
from queue import Queue
from light9.vidref.replay import framerate, songDir, takeDir, snapshotDir
from typing import Set

from IPython.core import ultratb
sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=1)

log = logging.getLogger()


class GstSource:

    def __init__(self, dev):
        """
        make new gst pipeline
        """
        Gst.init(None)
        self.liveImages = BehaviorSubject((0, None))

        size = [800, 600]

        log.info("new pipeline using device=%s" % dev)
        
        # using videocrop breaks the pipeline, may be this issue
        # https://gitlab.freedesktop.org/gstreamer/gst-plugins-bad/issues/732
        pipeStr = f"v4l2src device=\"{dev}\" ! videoconvert ! appsink emit-signals=true max-buffers=1 drop=true name=end0 caps=video/x-raw,format=RGB,width={size[0]},height={size[1]}"
        log.info("pipeline: %s" % pipeStr)

        self.pipe = Gst.parse_launch(pipeStr)

        self.setupPipelineError(self.pipe, self.onError)

        self.appsink = self.pipe.get_by_name('end0')
        self.appsink.connect('new-sample', self.new_sample)

        self.pipe.set_state(Gst.State.PLAYING)
        log.info('recording video')

    def new_sample(self, appsink):
        try:
            sample = appsink.emit('pull-sample')
            caps = sample.get_caps()
            buf = sample.get_buffer()
            (result, mapinfo) = buf.map(Gst.MapFlags.READ)
            try:
                img = Image.frombytes(
                    'RGB', (caps.get_structure(0).get_value('width'),
                            caps.get_structure(0).get_value('height')),
                    mapinfo.data)
                img = img.crop((0, 100, 800,  500))
            finally:
                buf.unmap(mapinfo)
            self.liveImages.on_next((time.time(), img))
        except Exception:
            traceback.print_exc()
        return Gst.FlowReturn.OK

    def setupPipelineError(self, pipe, cb):
        bus = pipe.get_bus()

        def onBusMessage(bus, msg):

            print('nusmsg', msg)
            if msg.type == Gst.MessageType.ERROR:
                _, txt = msg.parse_error()
                cb(txt)
            return True

        # not working; use GST_DEBUG=4 to see errors
        bus.add_watch(0, onBusMessage)
        bus.connect('message', onBusMessage)

    def onError(self, messageText):
        if ('v4l2src' in messageText and
            ('No such file or directory' in messageText or
             'Resource temporarily unavailable' in messageText or
             'No such device' in messageText)):
            log.error(messageText)
            os.abort()
        else:
            log.error("ignoring error: %r" % messageText)


class oldPipeline(object):

    def __init__(self):
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


'''
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
'''
