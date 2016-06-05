log = console.log

# Patch is {addQuads: <quads>, delQuads: <quads>}
# <quads> is [{subject: s, ...}, ...]

# (sloppily shared to rdfdbclient.coffee too)
window.patchSizeSummary = (patch) ->
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
    handle = {s: s, p: p, func: onChange}
    return handle
    
  unsubscribe: (subscription) ->
    spList = @handlersSp[subscription.s][subscription.p]
    i = spList.indexOf(subscription.func)
    if i == -1
      throw new Error('subscription not found')
    spList.splice(i, 1)

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
    handle = @_watchers.subscribe(s, p, o, onChange)
    immediatePatch = {delQuads: [], addQuads: @graph.findByIRI(s, p, o)}
    if immediatePatch.addQuads.length
      onChange(immediatePatch)
    return handle

  unsubscribe: (subscription) ->
    @_watchers.unsubscribe(subscription)

  _singleValue: (s, p) ->
    quads = @graph.findByIRI(s, p)
    switch quads.length
      when 0
        throw new Error("no value for "+s+" "+p)
      when 1
        obj = quads[0].object
        return obj
      else
        throw new Error("too many values: " + JSON.stringify(quads))

  floatValue: (s, p) ->
    parseFloat(N3.Util.getLiteralValue(@_singleValue(s, p)))
    
  stringValue: (s, p) ->
    N3.Util.getLiteralValue(@_singleValue(s, p))
    
  uriValue: (s, p) ->
    @_singleValue(s, p)

  objects: (s, p) ->
    quads = @graph.findByIRI(s, p)
    return (q.object for q in quads)

  subjects: (p, o) ->

  items: (list) ->

  contains: (s, p, o) ->

