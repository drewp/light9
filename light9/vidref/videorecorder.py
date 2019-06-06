from dataclasses import dataclass
from io import BytesIO
from typing import Optional
import time, logging, os, traceback

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')

from gi.repository import Gst
from greplin import scales
from rdflib import URIRef
from rx.subject import BehaviorSubject
from twisted.internet import threads
import PIL.Image
import moviepy.editor
import numpy

from light9 import showconfig
from light9.ascoltami.musictime_client import MusicTime
from light9.newtypes import Song

log = logging.getLogger()

stats = scales.collection(
    '/recorder',
    scales.PmfStat('jpegEncode', recalcPeriod=1),
    scales.IntStat('deletes'),
    scales.PmfStat('waitForNextImg', recalcPeriod=1),
    scales.PmfStat('crop', recalcPeriod=1),
    scales.RecentFpsStat('encodeFrameFps'),
    scales.RecentFpsStat('queueGstFrameFps'),
)


@dataclass
class CaptureFrame:
    img: PIL.Image
    song: Song
    t: float
    isPlaying: bool
    imgJpeg: Optional[bytes] = None

    @stats.jpegEncode.time()
    def asJpeg(self):
        if not self.imgJpeg:
            output = BytesIO()
            self.img.save(output, 'jpeg', quality=80)
            self.imgJpeg = output.getvalue()
        return self.imgJpeg


def songDir(song: Song) -> bytes:
    return os.path.join(
        showconfig.root(), b'video',
        song.replace('http://', '').replace('/', '_').encode('ascii'))


def takeUri(songPath: bytes) -> URIRef:
    p = songPath.decode('ascii').split('/')
    take = p[-1].replace('.mp4', '')
    song = p[-2].split('_')
    return URIRef('/'.join(
        ['http://light9.bigasterisk.com/show', song[-2], song[-1], take]))


def deleteClip(uri: URIRef):
    # uri http://light9.bigasterisk.com/show/dance2019/song6/take_155
    # path show/dance2019/video/light9.bigasterisk.com_show_dance2019_song6/take_155.*
    w = uri.split('/')[-4:]
    path = '/'.join([
        w[0], w[1], 'video', f'light9.bigasterisk.com_{w[0]}_{w[1]}_{w[2]}',
        w[3]
    ])
    log.info(f'deleting {uri} {path}')
    stats.deletes += 1
    for fn in [path + '.mp4', path + '.timing']:
        os.remove(fn)


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

    def __init__(self, frames: BehaviorSubject, root: bytes):
        self.frames = frames
        self.root = root
        self.nextImg: Optional[CaptureFrame] = None

        self.currentOutputClip: Optional[moviepy.editor.VideoClip] = None
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
            self.save(
                os.path.join(songDir(cf.song), b'take_%d' % int(time.time())))
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

    def _bg_save(self, outBase: bytes):
        os.makedirs(os.path.dirname(outBase), exist_ok=True)
        self.frameMap = open(outBase + b'.timing', 'wt')

        # todo: see moviestore.py for a better-looking version where
        # we get to call write_frame on a FFMPEG_VideoWriter instead
        # of it calling us back.

        self.currentClipFrameCount = 0

        # (immediately calls make_frame)
        self.currentOutputClip = moviepy.editor.VideoClip(self._bg_make_frame,
                                                          duration=999.)
        # The fps recorded in the file doesn't matter much; we'll play
        # it back in sync with the music regardless.
        self.currentOutputClip.fps = 10
        log.info(f'write_videofile {outBase} start')
        try:
            self.outMp4 = outBase.decode('ascii') + '.mp4'
            self.currentOutputClip.write_videofile(self.outMp4,
                                                   codec='libx264',
                                                   audio=False,
                                                   preset='ultrafast',
                                                   logger=None,
                                                   ffmpeg_params=['-g', '10'],
                                                   bitrate='150000')
        except (StopIteration, RuntimeError):
            self.frameMap.close()

        log.info('write_videofile done')
        self.currentOutputClip = None

        if self.currentClipFrameCount < 400:
            log.info('too small- deleting')
            deleteClip(takeUri(self.outMp4.encode('ascii')))

    def _bg_make_frame(self, video_time_secs):
        stats.encodeFrameFps.mark()
        if self.nextWriteAction == 'close':
            raise StopIteration  # the one in write_videofile
        elif self.nextWriteAction == 'notWritingClip':
            raise NotImplementedError
        elif self.nextWriteAction == 'saveFrames':
            pass
        else:
            raise NotImplementedError(self.nextWriteAction)

        # should be a little queue to miss fewer frames
        t1 = time.time()
        while self.nextImg is None:
            time.sleep(.015)
        stats.waitForNextImg = time.time() - t1
        cf, self.nextImg = self.nextImg, None

        self.frameMap.write(f'video {video_time_secs:g} = song {cf.t:g}\n')
        self.currentClipFrameCount += 1
        return numpy.asarray(cf.img)


class GstSource:

    def __init__(self, dev):
        """
        make new gst pipeline
        """
        Gst.init(None)
        self.musicTime = MusicTime(pollCurvecalc=False)
        self.liveImages: BehaviorSubject = BehaviorSubject(
            None)  # stream of Optional[CaptureFrame]

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
                img = PIL.Image.frombytes(
                    'RGB', (caps.get_structure(0).get_value('width'),
                            caps.get_structure(0).get_value('height')),
                    mapinfo.data)
                img = self.crop(img)
            finally:
                buf.unmap(mapinfo)
            # could get gst's frame time and pass it to getLatest
            latest = self.musicTime.getLatest()
            if 'song' in latest:
                stats.queueGstFrameFps.mark()
                self.liveImages.on_next(
                    CaptureFrame(img=img,
                                 song=Song(latest['song']),
                                 t=latest['t'],
                                 isPlaying=latest['playing']))
        except Exception:
            traceback.print_exc()
        return Gst.FlowReturn.OK

    @stats.crop.time()
    def crop(self, img):
        return img.crop((0, 100, 640, 380))

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


'''
class oldPipeline(object):

    def __init__(self):
        self.snapshotRequests = Queue()

    def snapshot(self):
        """
        returns deferred to the path (which is under snapshotDir()) where
        we saved the image. This callback comes from another thread,
        but I haven't noticed that being a problem yet.
        """
        d = defer.Deferred()

        def req(frame):
            filename = "%s/%s.jpg" % ('todo', time.time())
            log.debug("received snapshot; saving in %s", filename)
            frame.save(filename)
            d.callback(filename)

        log.debug("requesting snapshot")
        self.snapshotRequests.put(req)
        return d


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
