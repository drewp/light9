#!/usr/bin/python
"""
alternate to the mpd music player, for ascoltami
"""

import time, logging, traceback
from gi.repository import Gst
from twisted.internet import task

log = logging.getLogger()


class Player(object):

    def __init__(self, autoStopOffset=4, onEOS=None):
        """autoStopOffset is the number of seconds before the end of
        song before automatically stopping (which is really pausing).
        onEOS is an optional function to be called when we reach the
        end of a stream (for example, can be used to advance the song).
        It is called with one argument which is the URI of the song that
        just finished."""
        self.autoStopOffset = autoStopOffset
        self.playbin = self.pipeline = Gst.ElementFactory.make('playbin', None)

        self.playStartTime = 0
        self.lastWatchTime = 0
        self.autoStopTime = 0
        self.lastSetSongUri = None
        self.onEOS = onEOS

        task.LoopingCall(self.watchTime).start(.050)

        #bus = self.pipeline.get_bus()
        # not working- see notes in pollForMessages
        #self.watchForMessages(bus)

    def watchTime(self):
        try:
            self.pollForMessages()

            t = self.currentTime()
            log.debug("watch %s < %s < %s", self.lastWatchTime,
                      self.autoStopTime, t)
            if self.lastWatchTime < self.autoStopTime < t:
                log.info("autostop")
                self.pause()

            self.lastWatchTime = t
        except Exception:
            traceback.print_exc()

    def watchForMessages(self, bus):
        """this would be nicer than pollForMessages but it's not working for
        me. It's like add_signal_watch isn't running."""
        bus.add_signal_watch()

        def onEos(*args):
            print("onEos", args)
            if self.onEOS is not None:
                self.onEOS(self.getSong())

        bus.connect('message::eos', onEos)

        def onStreamStatus(bus, message):
            print("streamstatus", bus, message)
            (statusType, _elem) = message.parse_stream_status()
            if statusType == Gst.StreamStatusType.ENTER:
                self.setupAutostop()

        bus.connect('message::stream-status', onStreamStatus)

    def pollForMessages(self):
        """bus.add_signal_watch seems to be having no effect, but this works"""
        bus = self.pipeline.get_bus()
        mt = Gst.MessageType
        msg = bus.poll(
            mt.EOS | mt.STREAM_STATUS | mt.ERROR,  # | mt.ANY,
            0)
        if msg is not None:
            log.debug("bus message: %r %r", msg.src, msg.type)
            # i'm trying to catch here a case where the pulseaudio
            # output has an error, since that's otherwise kind of
            # mysterious to diagnose. I don't think this is exactly
            # working.
            if msg.type == mt.ERROR:
                log.error(repr(msg.parse_error()))
            if msg.type == mt.EOS:
                if self.onEOS is not None:
                    self.onEOS(self.getSong())
            if msg.type == mt.STREAM_STATUS:
                (statusType, _elem) = msg.parse_stream_status()
                if statusType == Gst.StreamStatusType.ENTER:
                    self.setupAutostop()

    def seek(self, t):
        isSeekable = self.playbin.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE | Gst.SeekFlags.SKIP,
            t * Gst.SECOND)
        if not isSeekable:
            raise ValueError('seek_simple failed')
        self.playStartTime = time.time()

    def setSong(self, songLoc, play=True):
        """
        uri like file:///my/proj/light9/show/dance2010/music/07.wav
        """
        log.info("set song to %r" % songLoc)
        self.pipeline.set_state(Gst.State.READY)
        self.preload(songLoc)
        self.pipeline.set_property("uri", songLoc)
        self.lastSetSongUri = songLoc
        # todo: don't have any error report yet if the uri can't be read
        if play:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.playStartTime = time.time()

    def getSong(self):
        """Returns the URI of the current song."""
        # even the 'uri' that I just set isn't readable yet
        return self.playbin.get_property("uri") or self.lastSetSongUri

    def preload(self, songPath):
        """
        to avoid disk seek stutters, which happened sometimes (in 2007) with the
        non-gst version of this program, we read the whole file to get
        more OS caching.

        i don't care that it's blocking.
        """
        log.info("preloading %s", songPath)
        assert songPath.startswith("file://"), songPath
        try:
            open(songPath[len("file://"):], 'rb').read()
        except IOError as e:
            log.error("couldn't preload %s, %r", songPath, e)
            raise

    def currentTime(self):
        success, cur = self.playbin.query_position(Gst.Format.TIME)
        if not success:
            return 0
        return cur / Gst.SECOND

    def duration(self):
        success, dur = self.playbin.query_duration(Gst.Format.TIME)
        if not success:
            return 0
        return dur / Gst.SECOND

    def states(self):
        """json-friendly object describing the interesting states of
        the player nodes"""
        success, state, pending = self.playbin.get_state(timeout=0)
        return {
            "current": {
                "name": state.value_nick
            },
            "pending": {
                "name": state.value_nick
            }
        }

    def pause(self):
        self.pipeline.set_state(Gst.State.PAUSED)

    def isAutostopped(self):
        """
        are we stopped at the autostop time?
        """
        pos = self.currentTime()
        autoStop = self.duration() - self.autoStopOffset
        return not self.isPlaying() and abs(
            pos - autoStop) < 1  # i've seen .4 difference here

    def resume(self):
        self.pipeline.set_state(Gst.State.PLAYING)

    def setupAutostop(self):
        dur = self.duration()
        if dur == 0:
            raise ValueError("duration=0, can't set autostop")
        self.autoStopTime = (dur - self.autoStopOffset)
        log.info("autostop will be at %s", self.autoStopTime)
        # pipeline.seek can take a stop time, but using that wasn't
        # working out well. I'd get pauses at other times that were
        # hard to remove.

    def isPlaying(self):
        _, state, _ = self.pipeline.get_state(timeout=0)
        return state == Gst.State.PLAYING
