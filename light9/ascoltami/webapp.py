import json, socket, subprocess, cyclone.web, os
from twisted.python.util import sibpath
from twisted.python.filepath import FilePath
from light9.namespaces import L9
from light9.showconfig import getSongsFromShow, songOnDisk
from rdflib import URIRef
from web.contrib.template import render_genshi
render = render_genshi([sibpath(__file__, ".")], auto_reload=True)

from lib.cycloneerr import PrettyErrorHandler

_songUris = {} # locationUri : song
def songLocation(graph, songUri):
    loc = URIRef("file://%s" % songOnDisk(songUri))
    _songUris[loc] = songUri
    return loc
    
def songUri(graph, locationUri):
    return _songUris[locationUri]

class root(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/xhtml+xml")
        # todo: use a template; embed the show name and the intro/post
        # times into the page
        self.write(render.index(host=socket.gethostname()))

def playerSongUri(graph, player):
    """or None"""
    
    playingLocation = player.getSong()
    if playingLocation:
        return songUri(graph, URIRef(playingLocation))
    else:
        return None

class timeResource(PrettyErrorHandler,cyclone.web.RequestHandler):
    def get(self):
        player = self.settings.app.player
        graph = self.settings.app.graph
        self.set_header("Content-Type", "application/json")

        if player.isAutostopped():
            nextAction = 'finish'
        elif player.isPlaying():
            nextAction = 'disabled'
        else:
            nextAction = 'play'

        self.write(json.dumps({
            "song" : playerSongUri(graph, player),
            "started" : player.playStartTime,
            "duration" : player.duration(),
            "playing" : player.isPlaying(),
            "t" : player.currentTime(),
            "state" : player.states(),
            "next" : nextAction,
            }))

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

class songs(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        graph = self.settings.app.graph

        songs = getSongsFromShow(graph, self.settings.app.show)

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"songs" : [
            {"uri" : s,
             "path" : graph.value(s, L9['showPath']),
             "label" : graph.label(s)} for s in songs]}))

class songResource(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self):
        """post a uri of song to switch to (and start playing)"""
        graph = self.settings.app.graph

        self.settings.app.player.setSong(songLocation(graph, URIRef(self.request.body)))
        self.set_header("Content-Type", "text/plain")
        self.write("ok")
    
class seekPlayOrPause(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self):
        player = self.settings.app.player

        data = json.loads(self.request.body)
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
        graph, player = self.settings.app.graph, self.settings.app.player

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
        (r"/song", songResource),
        (r"/songs", songs),
        (r"/seekPlayOrPause", seekPlayOrPause),
        (r"/output", output),
        (r"/go", goButton),
        ], app=app)

