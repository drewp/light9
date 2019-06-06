import json, socket, subprocess, os, logging, time

from cyclone import template
from rdflib import URIRef
import cyclone.web, cyclone.websocket
from greplin.scales.cyclonehandler import StatsHandler

from cycloneerr import PrettyErrorHandler
from light9.namespaces import L9
from light9.showconfig import getSongsFromShow, songOnDisk
from twisted.internet import reactor
_songUris = {}  # locationUri : song
log = logging.getLogger()
loader = template.Loader(os.path.dirname(__file__))


def songLocation(graph, songUri):
    loc = URIRef("file://%s" % songOnDisk(songUri))
    _songUris[loc] = songUri
    return loc


def songUri(graph, locationUri):
    return _songUris[locationUri]


class root(PrettyErrorHandler, cyclone.web.RequestHandler):

    def get(self):
        self.set_header("Content-Type", "application/xhtml+xml")
        self.write(
            loader.load('index.html').generate(host=socket.gethostname(),
                                               times=json.dumps({
                                                   'intro': 4,
                                                   'post': 4
                                               })))


def playerSongUri(graph, player):
    """or None"""

    playingLocation = player.getSong()
    if playingLocation:
        return songUri(graph, URIRef(playingLocation))
    else:
        return None


def currentState(graph, player):
    if player.isAutostopped():
        nextAction = 'finish'
    elif player.isPlaying():
        nextAction = 'disabled'
    else:
        nextAction = 'play'

    return {
        "song": playerSongUri(graph, player),
        "started": player.playStartTime,
        "duration": player.duration(),
        "playing": player.isPlaying(),
        "t": player.currentTime(),
        "state": player.states(),
        "next": nextAction,
    }


class timeResource(PrettyErrorHandler, cyclone.web.RequestHandler):

    def get(self):
        player = self.settings.app.player
        graph = self.settings.app.graph
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(currentState(graph, player)))

    def post(self):
        """
        post a json object with {pause: true} or {resume: true} if you
        want those actions. Use {t: <seconds>} to seek, optionally
        with a pause/resume command too.
        """
        params = json.loads(self.request.body)
        player = self.settings.app.player
        if params.get('pause', False):
            player.pause()
        if params.get('resume', False):
            player.resume()
        if 't' in params:
            player.seek(params['t'])
        self.set_header("Content-Type", "text/plain")
        self.write("ok")


class timeStreamResource(cyclone.websocket.WebSocketHandler):

    def connectionMade(self, *args, **kwargs) -> None:
        self.lastSent = None
        self.lastSentTime = 0.
        self.loop()

    def loop(self):
        now = time.time()
        msg = currentState(self.settings.app.graph, self.settings.app.player)
        if msg != self.lastSent or now > self.lastSentTime + 2:
            self.sendMessage(json.dumps(msg))
            self.lastSent = msg
            self.lastSentTime = now

        if self.transport.connected:
            reactor.callLater(.2, self.loop)

    def connectionLost(self, reason):
        log.info("bye ws client %r: %s", self, reason)


class songs(PrettyErrorHandler, cyclone.web.RequestHandler):

    def get(self):
        graph = self.settings.app.graph

        songs = getSongsFromShow(graph, self.settings.app.show)

        self.set_header("Content-Type", "application/json")
        self.write(
            json.dumps({
                "songs": [{
                    "uri": s,
                    "path": graph.value(s, L9['showPath']),
                    "label": graph.label(s)
                } for s in songs]
            }))


class songResource(PrettyErrorHandler, cyclone.web.RequestHandler):

    def post(self):
        """post a uri of song to switch to (and start playing)"""
        graph = self.settings.app.graph

        self.settings.app.player.setSong(
            songLocation(graph, URIRef(self.request.body.decode('utf8'))))
        self.set_header("Content-Type", "text/plain")
        self.write("ok")


class seekPlayOrPause(PrettyErrorHandler, cyclone.web.RequestHandler):
    """curveCalc's ctrl-p or a vidref scrub"""

    def post(self):
        player = self.settings.app.player

        data = json.loads(self.request.body)
        if 'scrub' in data:
            player.pause()
            player.seek(data['scrub'])
            return
        if 'action' in data:
            if data['action'] == 'play':
                player.resume()
            elif data['action'] == 'pause':
                player.pause()
            else:
                raise NotImplementedError
            return
        if player.isPlaying():
            player.pause()
        else:
            player.seek(data['t'])
            player.resume()


class output(PrettyErrorHandler, cyclone.web.RequestHandler):

    def post(self):
        d = json.loads(self.request.body)
        subprocess.check_call(["bin/movesinks", str(d['sink'])])


class goButton(PrettyErrorHandler, cyclone.web.RequestHandler):

    def post(self):
        """
        if music is playing, this silently does nothing.
        """
        player = self.settings.app.player

        if player.isAutostopped():
            player.resume()
        elif player.isPlaying():
            pass
        else:
            player.resume()

        self.set_header("Content-Type", "text/plain")
        self.write("ok")


def makeWebApp(app):
    return cyclone.web.Application(handlers=[
        (r"/", root),
        (r"/time", timeResource),
        (r"/time/stream", timeStreamResource),
        (r"/song", songResource),
        (r"/songs", songs),
        (r"/seekPlayOrPause", seekPlayOrPause),
        (r"/output", output),
        (r"/go", goButton),
        (r'/stats/(.*)', StatsHandler, {
            'serverName': 'ascoltami'
        }),
    ],
                                   app=app)
