#!/usr/bin/python

"""

dvcam test
gst-launch dv1394src ! dvdemux name=d ! dvdec ! ffmpegcolorspace ! hqdn3d ! xvimagesink

"""
import gobject, logging, traceback
import gtk
from twisted.python.util import sibpath
from light9.vidref.replay import ReplayViews, framerate
from light9.vidref.musictime import MusicTime
from light9.vidref.videorecorder import Pipeline
from light9.vidref import remotepivideo
log = logging.getLogger()

class Gui(object):
    def __init__(self, graph):
        wtree = gtk.Builder()
        wtree.add_from_file(sibpath(__file__, "vidref.glade"))
        mainwin = wtree.get_object("MainWindow")
        mainwin.connect("destroy", gtk.main_quit)
        wtree.connect_signals(self)
        gtk.rc_parse("theme/marble-ice/gtk-2.0/gtkrc")

        self.recordingTo = wtree.get_object('recordingTo')
        self.musicScale = wtree.get_object("musicScale")
        self.musicScale.connect("value-changed", self.onMusicScaleValue)
        # tiny race here if onMusicScaleValue tries to use musicTime right away
        self.musicTime = MusicTime(onChange=self.onMusicTimeChange)
        self.ignoreScaleChanges = False
        # self.attachLog(wtree.get_object("lastLog")) # disabled due to crashing

        # wtree.get_object("replayPanel").show() # demo only
        rp = wtree.get_object("replayVbox")
        self.replayViews = ReplayViews(rp)

        mainwin.show_all()
        vid3 = wtree.get_object("vid3")

        if 0:
            self.pipeline = Pipeline(
                liveVideoXid=vid3.window.xid,
                musicTime=self.musicTime,
                recordingTo=self.recordingTo)
        else:
            self.pipeline = remotepivideo.Pipeline(
                liveVideo=vid3,
                musicTime=self.musicTime,
                recordingTo=self.recordingTo,
                graph=graph)

        vid3.props.width_request = 360
        vid3.props.height_request = 220
        wtree.get_object("frame1").props.height_request = 220
        

        self.pipeline.setInput('v4l') # auto seems to not search for dv

        gobject.timeout_add(1000 // framerate, self.updateLoop)


    def snapshot(self):
        return self.pipeline.snapshot()
        
    def attachLog(self, textBuffer):
        """write log lines to this gtk buffer"""
        class ToBuffer(logging.Handler):
            def emit(self, record):
                textBuffer.set_text(record.getMessage())

        h = ToBuffer()
        h.setLevel(logging.INFO)
        log.addHandler(h)

    def updateLoop(self):
        position = self.musicTime.getLatest()
        try:
            with gtk.gdk.lock:
                self.replayViews.update(position)
        except:
            traceback.print_exc()
        return True

    def getInputs(self):
        return ['auto', 'dv', 'video0']


    def on_liveVideoEnabled_toggled(self, widget):
        self.pipeline.setLiveVideo(widget.get_active())
                                                   
    def on_liveFrameRate_value_changed(self, widget):
        print widget.get_value()

    def onMusicTimeChange(self, position):
        self.ignoreScaleChanges = True
        try:
            self.musicScale.set_range(0, position['duration'])
            self.musicScale.set_value(position['t'])
        finally:
            self.ignoreScaleChanges = False

    def onMusicScaleValue(self, scaleRange):
        """the scale position has changed. if it was by the user, send
        it back to music player"""
        if not self.ignoreScaleChanges:
            self.musicTime.sendTime(scaleRange.get_value())
