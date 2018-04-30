log = console.log

# for mocha
if require?
  `window = {}`
  `N3 = require('../../node_modules/n3/n3-browser.js')`
  module.exports = window


toJsonPatch = (jsPatch, cb) ->
  out = {patch: {adds: '', deletes: ''}}

  writeDels = (cb) ->
    writer = N3.Writer({ format: 'N-Quads' })
    writer.addTriples(jsPatch.delQuads)
    writer.end((err, result) ->
      out.patch.deletes = result
      cb())

  writeAdds = (cb) ->
    writer = N3.Writer({ format: 'N-Quads' })
    writer.addTriples(jsPatch.addQuads)
    writer.end((err, result) ->
      out.patch.adds = result
      cb())
    
  async.parallel([writeDels, writeAdds], (err) ->
      cb(JSON.stringify(out))
    )

parseJsonPatch = (jsonPatch, cb) ->
  # note response cb doesn't have an error arg.
  input = JSON.parse(jsonPatch)
  patch = {delQuads: [], addQuads: []}

  parseAdds = (cb) =>
    parser = N3.Parser()
    parser.parse input.patch.adds, (error, quad, prefixes) =>
                  if (quad)
                    patch.addQuads.push(quad)
                  else
                    cb()
  parseDels = (cb) =>
    parser = N3.Parser()
    parser.parse input.patch.deletes, (error, quad, prefixes) =>
                  if (quad)
                    patch.delQuads.push(quad)
                  else
                    cb()

  async.parallel([parseAdds, parseDels], ((err) => cb(patch)))

class window.RdfDbClient
  # Send and receive patches from rdfdb
  constructor: (@patchSenderUrl, @clearGraphOnNewConnection, @applyPatch, @setStatus) ->
    @_patchesToSend = []
    @_lastPingMs = -1
    @_patchesReceived = 0
    @_patchesSent = 0

    @_reconnectionTimeout = null
    @_newConnection()

  _updateStatus: ->
    ws = (if not @ws? then 'no' else switch @ws.readyState
      when @ws.CONNECTING then 'connecting'
      when @ws.OPEN then 'open'
      when @ws.CLOSING then 'closing'
      when @ws.CLOSED then 'close'
      )

    ping = if @_lastPingMs > 0 then @_lastPingMs else '...'
    @setStatus("#{ws};
      #{@_patchesReceived} recv;
      #{@_patchesSent} sent;
      #{@_patchesToSend.length} pending;
      #{ping}ms")
 
  sendPatch: (patch) ->
    console.log('rdfdbclient: queue patch to server ', patchSizeSummary(patch))
    @_patchesToSend.push(patch)
    @_updateStatus()
    @_continueSending()           

  _newConnection: ->
    wsOrWss = window.location.protocol.replace('http', 'ws')
    fullUrl = wsOrWss + '//' + window.location.host + @patchSenderUrl
    @ws.close() if @ws?
    @ws = new WebSocket(fullUrl)

    @ws.onopen = =>
      log('rdfdbclient: connected to', fullUrl)
      @_updateStatus()
      @clearGraphOnNewConnection()
      @_pingLoop()

    @ws.onerror = (e) =>
      log('rdfdbclient: ws error ' + e)
      @ws.onclose()

    @ws.onclose = =>
      log('rdfdbclient: ws close')
      @_updateStatus()
      clearTimeout(@_reconnectionTimeout) if @_reconnectionTimeout?
      @_reconnectionTimeout = setTimeout(@_newConnection.bind(@), 1000)

    @ws.onmessage = @_onMessage.bind(@)

  _pingLoop: () ->
    if @ws.readyState == @ws.OPEN
      @ws.send('PING')
      @_lastPingMs = -Date.now()
      
      clearTimeout(@_pingLoopTimeout) if @_pingLoopTimeout?
      @_pingLoopTimeout = setTimeout(@_pingLoop.bind(@), 10000)

  _onMessage: (evt) ->
    msg = evt.data
    if msg == 'PONG'
      @_lastPingMs = Date.now() + @_lastPingMs
      @_updateStatus()
      return
    parseJsonPatch(msg, @applyPatch.bind(@))
    @_patchesReceived++
    @_updateStatus()

  _continueSending: ->
    if @ws.readyState != @ws.OPEN
      setTimeout(@_continueSending.bind(@), 500)
      return

    # we could call this less often and coalesce patches together to optimize
    # the dragging cases.

    sendOne = (patch, cb) =>
        toJsonPatch(patch, (json) =>
          log('rdfdbclient: send patch to server, ' + json.length + ' bytes')
          @ws.send(json)
          @_patchesSent++
          @_updateStatus()
          cb(null)
      )

    async.eachSeries(@_patchesToSend, sendOne, () =>
        @_patchesToSend = []
        @_updateStatus()
      )
