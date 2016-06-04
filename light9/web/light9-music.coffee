log = console.log

# port of light9/curvecalc/musicaccess.py
Polymer
  is: "light9-music",
  properties:
    status: { type: String, notify: true }
    duration: { type: Number, notify: true }
    playing: { type: Boolean, notify: true }
    song: { type: String, notify: true }
    t: { type: Number, notify: true }
  ready: ->
    @$.getTime.addEventListener('response', @onResponse.bind(@))
    @$.getTime.addEventListener 'error', (e) =>
      req = @$.getTime.lastRequest
      @status = "GET "+req.url+ " -> " + req.status + " " + req.statusText
      setTimeout(@poll.bind(@), 2000)
    @poll()
  poll: ->
    @$.getTime.generateRequest()
    @status = "poll"
  onResponse: ->
    @status = "ok"
    setTimeout(@poll.bind(@), 1000)
    r = @$.getTime.lastResponse
    @duration = r.duration
    @playing = r.playing
    @song = r.song
    @t = r.t
