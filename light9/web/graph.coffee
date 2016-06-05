log = console.log

# Patch is {addQuads: <quads>, delQuads: <quads>}
# <quads> is [{subject: s, ...}, ...]

patchSizeSummary = (patch) ->
  '-' + patch.delQuads.length + ' +' + patch.addQuads.length

# partial port of autodepgraphapi.py
class GraphWatchers
  constructor: ->
    @handlersSp = {} # {s: {p: [handlers]}}
  subscribe: (s, p, o, onChange) -> # return subscription handle
    if o? then throw Error('not implemented')
    if not @handlersSp[s]
      @handlersSp[s] = {}
    if not @handlersSp[s][p]
      @handlersSp[s][p] = []
    @handlersSp[s][p].push(onChange)
    
  unsubscribe: (subscription) ->
    throw Error('not implemented')

  matchingHandlers: (quad) ->
    matches = []
    for subjDict in [@handlersSp[quad.subject] || {}, @handlersSp[null] || {}]
      for subjPredMatches in [subjDict[quad.predicate] || [], subjDict[null] || []]
        matches = matches.concat(subjPredMatches)
    return matches
    
  graphChanged: (patch) ->
    for quad in patch.delQuads
      for cb in @matchingHandlers(quad)
        # currently calls multiple times, which is ok, but we might
        # group things into fewer patches
        cb({delQuads: [quad], addQuads: []})
    for quad in patch.addQuads
      for cb in @matchingHandlers(quad)
        cb({delQuads: [], addQuads: [quad]})


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

class RdfDbClient
  # Send and receive patches from rdfdb
  constructor: (@patchSenderUrl, @clearGraph, @applyPatch, @setStatus) ->
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
      #{@_patchesReceived} recv
      #{@_patchesSent} sent
      #{@_patchesToSend.length} pending;
      #{ping}ms")
 
  sendPatch: (patch) ->
    console.log('queue patch to server ', patchSizeSummary(patch))
    @_patchesToSend.push(patch)
    @_updateStatus()
    @_continueSending()           

  _newConnection: ->
    fullUrl = 'ws://' + window.location.host + @patchSenderUrl
    @ws.close() if @ws?
    @ws = new WebSocket(fullUrl)

    @ws.onopen = =>
      log('connected to', fullUrl)
      @_updateStatus()
      @clearGraph()
      @_pingLoop()

    @ws.onerror = (e) =>
      log('ws error ' + e)
      @ws.onclose()

    @ws.onclose = =>
      log('ws close')
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
          log('send patch to server, ' + json.length + ' bytes')
          @ws.send(json)
          @_patchesSent++
          @_updateStatus()
          cb(null)
      )

    async.eachSeries(@_patchesToSend, sendOne, () =>
        @_patchesToSend = []
        @_updateStatus()
      )

class window.SyncedGraph
  # Main graph object for a browser to use. Syncs both ways with
  # rdfdb. Meant to hide the choice of RDF lib, so we can change it
  # later.
  # 
  # Note that _applyPatch is the only method to write to the graph, so
  # it can fire subscriptions.

  constructor: (@patchSenderUrl, @prefixes, @setStatus) ->
    # patchSenderUrl is the /syncedGraph path of an rdfdb server.
    # prefixes can be used in Uri(curie) calls.
    @_watchers = new GraphWatchers()
    @clearGraph()

    @_client = new RdfDbClient(@patchSenderUrl, @clearGraph.bind(@),
                               @_applyPatch.bind(@), @setStatus)
    
  clearGraph: ->
    log('SyncedGraph clear')
    if @graph?
      @_applyPatch({addQuads: [], delQuads: @graph.find()})

    # if we had a Store already, this lets N3.Store free all its indices/etc
    @graph = N3.Store()
    @_addPrefixes(@prefixes)
    
      
  _addPrefixes: (prefixes) ->
    @graph.addPrefixes(prefixes)
        
  Uri: (curie) ->
    N3.Util.expandPrefixedName(curie, @graph._prefixes)

  Literal: (jsValue) ->
    N3.Util.createLiteral(jsValue)

  LiteralRoundedFloat: (f) ->
    N3.Util.createLiteral(d3.format(".3f")(f),
                          "http://www.w3.org/2001/XMLSchema#decimal")

  toJs: (literal) ->
    # incomplete
    parseFloat(N3.Util.getLiteralValue(literal))

  loadTrig: (trig, cb) -> # for debugging
    patch = {delQuads: [], addQuads: []}
    parser = N3.Parser()
    parser.parse trig, (error, quad, prefixes) =>
                  if (quad)
                    patch.addQuads.push(quad)
                  else
                    @_applyPatch(patch)
                    @_addPrefixes(prefixes)
                    cb() if cb
                    
  quads: () -> # for debugging
    [q.subject, q.predicate, q.object, q.graph] for q in @graph.find()

  applyAndSendPatch: (patch, cb) ->
    @_applyPatch(patch)
    @_client.sendPatch(patch)

  _applyPatch: (patch) ->
    # In most cases you want applyAndSendPatch.
    # 
    # This is the only method that writes to @graph!
    for quad in patch.delQuads
      @graph.removeTriple(quad)
    for quad in patch.addQuads
      @graph.addTriple(quad)
    log('applied patch locally', patchSizeSummary(patch))
    @_watchers.graphChanged(patch)

  getObjectPatch: (s, p, newObject, g) ->
    # send a patch which removes existing values for (s,p,*,c) and
    # adds (s,p,newObject,c). Values in other graphs are not affected.
    existing = @graph.findByIRI(s, p, null, g)
    return {
      delQuads: existing,
      addQuads: [{subject: s, predicate: p, object: newObject, graph: g}]
    }

  patchObject: (s, p, newObject, g) ->
    @applyAndSendPatch(@getObjectPatch(s, p, newObject, g))
  

  subscribe: (s, p, o, onChange) -> # return subscription handle
    # onChange is called with a patch that's limited to the quads
    # that match your request.
    # We call you immediately on existing triples.
    @_watchers.subscribe(s, p, o, onChange)
    immediatePatch = {delQuads: [], addQuads: @graph.findByIRI(s, p, o)}
    if immediatePatch.addQuads.length
      onChange(immediatePatch)

  unsubscribe: (subscription) ->
    @_watchers.unsubscribe(subscription)

  _singleValue: (s, p) ->
    quads = @graph.findByIRI(s, p)
    switch quads.length
      when 0
        throw new Error("no value for "+s+" "+p)
      when 1
        obj = quads[0].object
        return N3.Util.getLiteralValue(obj)
      else
        throw new Error("too many values: " + JSON.stringify(quads))

  floatValue: (s, p) ->
    parseFloat(@_singleValue(s, p))
    
  stringValue: (s, p) ->
    @_singleValue(s, p)
    
  uriValue: (s, p) ->

  objects: (s, p) ->

  subjects: (p, o) ->

  items: (list) ->

  contains: (s, p, o) ->

