log = console.log

# port of light9/curvecalc/musicaccess.py
Polymer
  is: "light9-music",
  properties:
    status: { type: String, notify: true }
    statusTitle: { type: String, notify: true }
    turboSign: { type: String, notify: true }
    
    duration: { type: Number, notify: true }
    song: { type: String, notify: true }
    # It does not yet work to write back to the playing/t
    # properties. See seekPlayOrPause.
    playing: { type: Boolean, notify: true }
    t: { type: Number, notify: true }
    
  ready: ->
    @turboUntil = 0
    @$.getTime.addEventListener('response', @onResponse.bind(@))
    @$.getTime.addEventListener 'error', (e) =>
      req = @$.getTime.lastRequest
      @status = "✘"
      @statusTitle = "GET "+req.url+ " -> " + req.status + " " + req.statusText
      setTimeout(@poll.bind(@), 2000)
    @poll()
    setInterval(@estimateTimeLoop.bind(@), 30)
    
  estimateTimeLoop: ->
    if @playing
      @t = @remoteT + (Date.now() - @remoteAsOfMs) / 1000
    else
      @t = @remoteT
    
  poll: ->
    clearTimeout(@nextPoll) if @nextPoll
    @$.getTime.generateRequest()
    @status = "♫"
    
  onResponse: ->
    @status = " "
    @lastResponse = @$.getTime.lastResponse
    now = Date.now()
    if !@lastResponse.playing && @lastResponse.t != @remoteT
      # likely seeking in another tool
      @turboUntil = now + 1000
    if now < @turboUntil
      @turboSign = "⚡"
      delay = 20
    else
      @turboSign = " "
      delay = 700
    
    @nextPoll = setTimeout(@poll.bind(@), delay)
    @duration = @lastResponse.duration
    @playing = @lastResponse.playing
    @song = @lastResponse.song

    @remoteT = @lastResponse.t
    @remoteAsOfMs = now

  seekPlayOrPause: (t) ->
    @$.seek.body = {t: t}
    @$.seek.generateRequest()
    
    @turboUntil = Date.now() + 1000
    @poll()
    
