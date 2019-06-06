from dataclasses import dataclass
from queue import Queue
from typing import Optional
import time, logging, os, traceback, sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')

from PIL import Image
from gi.repository import Gst
from rx.subject import BehaviorSubject
from twisted.internet import threads
import moviepy.editor
import numpy

from light9.ascoltami.musictime_client import MusicTime
from light9.newtypes import Song

from IPython.core import ultratb
sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=1)

log = logging.getLogger()


@dataclass(frozen=True)
class CaptureFrame:
    img: Image
    song: Song
    t: float
    isPlaying: bool


class FramesToVideoFiles:
    """

    nextWriteAction: 'ignore'
    currentOutputClip: None

    (frames come in for new video)
    nextWriteAction: 'saveFrame'
    currentOutputClip: new VideoClip
    (many frames)

    (music stops or song changes)
    nextWriteAction: 'close'
    currentOutputClip: None
    nextWriteAction: 'ignore'
    
    """

    def __init__(self, frames: BehaviorSubject):
        self.frames = frames
        self.nextImg: Optional[CaptureFrame] = None

        self.currentOutputClip = None
        self.currentOutputSong: Optional[Song] = None
        self.nextWriteAction = 'ignore'
        self.frames.subscribe(on_next=self.onFrame)

    def onFrame(self, cf: Optional[CaptureFrame]):
        if cf is None:
            return
        self.nextImg = cf

        if self.currentOutputClip is None and cf.isPlaying:
            # start up
            self.nextWriteAction = 'saveFrames'
            self.currentOutputSong = cf.song
            self.save('/tmp/out%s' % time.time())
        elif self.currentOutputClip and cf.isPlaying:
            self.nextWriteAction = 'saveFrames'
            # continue recording this
        elif self.currentOutputClip is None and not cf.isPlaying:
            self.nextWriteAction = 'notWritingClip'
            pass  # continue waiting
        elif self.currentOutputClip and not cf.isPlaying or self.currentOutputSong != cf.song:
            # stop
            self.nextWriteAction = 'close'
        else:
            raise NotImplementedError(str(vars()))

    def save(self, outBase):
        """
        receive frames (infinite) and wall-to-song times (stream ends with
        the song), and write a video file and a frame map
        """
        return threads.deferToThread(self._bg_save, outBase)

    def _bg_save(self, outBase):
        os.makedirs(os.path.dirname(outBase), exist_ok=True)
        self.frameMap = open(outBase + '.timing', 'wt')

        # (immediately calls make_frame)
        self.currentOutputClip = moviepy.editor.VideoClip(self._bg_make_frame,
                                                          duration=999.)
        # The fps recorded in the file doesn't matter much; we'll play
        # it back in sync with the music regardless.
        self.currentOutputClip.fps = 10
        log.info(f'write_videofile {outBase} start')
        try:
            self.currentOutputClip.write_videofile(outBase + '.mp4',
                                                   audio=False,
                                                   preset='ultrafast',
                                                   logger=None,
                                                   bitrate='150000')
        except (StopIteration, RuntimeError):
            self.frameMap.close()

        log.info('write_videofile done')
        self.currentOutputClip = None

    def _bg_make_frame(self, video_time_secs):
        if self.nextWriteAction == 'close':
            raise StopIteration  # the one in write_videofile
        elif self.nextWriteAction == 'notWritingClip':
            raise NotImplementedError
        elif self.nextWriteAction == 'saveFrames':
            pass
        else:
            raise NotImplementedError(self.nextWriteAction)

        # should be a little queue to miss fewer frames
        while self.nextImg is None:
            time.sleep(.03)
        cf, self.nextImg = self.nextImg, None

        self.frameMap.write(f'video {video_time_secs:g} = song {cf.t:g}\n')
        return numpy.asarray(cf.img)


class GstSource:

    def __init__(self, dev):
        """
        make new gst pipeline
        """
        Gst.init(None)
        self.musicTime = MusicTime(pollCurvecalc=False)
        self.liveImages: BehaviorSubject[
            Optional[CaptureFrame]] = BehaviorSubject(None)

        size = [640, 480]

        log.info("new pipeline using device=%s" % dev)

        # using videocrop breaks the pipeline, may be this issue
        # https://gitlab.freedesktop.org/gstreamer/gst-plugins-bad/issues/732
        pipeStr = (
            #f"v4l2src device=\"{dev}\""
            f'autovideosrc'
            f" ! videoconvert"
            f" ! appsink emit-signals=true max-buffers=1 drop=true name=end0 caps=video/x-raw,format=RGB,width={size[0]},height={size[1]}"
        )
        log.info("pipeline: %s" % pipeStr)

        self.pipe = Gst.parse_launch(pipeStr)

        self.setupPipelineError(self.pipe, self.onError)

        self.appsink = self.pipe.get_by_name('end0')
        self.appsink.connect('new-sample', self.new_sample)

        self.pipe.set_state(Gst.State.PLAYING)
        log.info('gst pipeline is recording video')

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
                img = img.crop((0, 100, 640, 380))
            finally:
                buf.unmap(mapinfo)
            # could get gst's frame time and pass it to getLatest
            latest = self.musicTime.getLatest()
            if 'song' in latest:
                self.liveImages.on_next(
                    CaptureFrame(img, Song(latest['song']), latest['t'],
                                 latest['playing']))
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
