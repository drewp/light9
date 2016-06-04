log = console.log

# port of light9/curvecalc/musicaccess.py
Polymer
  is: "light9-music",
  properties:
    status: { type: String, notify: true }
    statusTitle: { type: String, notify: true }
    turboSign: { type: String, notify: true }
    
    duration: { type: Number, notify: true }
    playing: { type: Boolean, notify: true }
    song: { type: String, notify: true }
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
    setInterval(@estimateTimeLoop.bind(@), 50)

  estimateTimeLoop: ->
    if @playing
      @t = @remoteT + (Date.now() - @remoteAsOfMs) / 1000
    else
      @t = @remoteT
    
  poll: ->
    @$.getTime.generateRequest()
    @status = "♫"
  onResponse: ->
    @status = " "
    r = @$.getTime.lastResponse
    now = Date.now()
    if !r.playing && r.t != @remoteT
      # likely seeking in another tool
      @turboUntil = now + 1000
    if now < @turboUntil
      @turboSign = "⚡"
      delay = 20
    else
      @turboSign = " "
      delay = 700
    
    setTimeout(@poll.bind(@), delay)
    @duration = r.duration
    @playing = r.playing
    @song = r.song

    @remoteT = r.t
    @remoteAsOfMs = now

    

    
