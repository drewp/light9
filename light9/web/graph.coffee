log = console.log

# Patch is {addQuads: <quads>, delQuads: <quads>}
# <quads> is [{subject: s, ...}, ...]

# for mocha
if require?
  `window = {}`
  `N3 = require('./lib/N3.js-pull61/N3.js')`
  `d3 = require('./lib/d3/build/d3.min.js')`
  `RdfDbClient = require('./rdfdbclient.js').RdfDbClient`
  module.exports = window

RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'

patchSizeSummary = (patch) ->
  '-' + patch.delQuads.length + ' +' + patch.addQuads.length

# (sloppily shared to rdfdbclient.coffee too)
window.patchSizeSummary = patchSizeSummary

class Handler
  # a function and the quad patterns it cared about
  constructor: (@func, @label) ->
    @patterns = [] # s,p,o,g quads that should trigger the next run
    @innerHandlers = [] # Handlers requested while this one was running
  
class AutoDependencies
  constructor: () ->
    @handlers = new Handler(null) # tree of all known Handlers (at least those with non-empty patterns). Top node is not a handler.
    @handlerStack = [@handlers] # currently running
    
  runHandler: (func, label) ->
    # what if we have this func already? duplicate is safe?

    if not label?
      throw new Error("missing label")

    h = new Handler(func, label)
    tailChildren = @handlerStack[@handlerStack.length - 1].innerHandlers
    matchingLabel = _.filter(tailChildren, ((c) -> c.label == label)).length
    # ohno, something depends on some handlers getting run twice :(
    if matchingLabel < 2
      tailChildren.push(h)
    console.time("handler #{label}")
    @_rerunHandler(h, null)
    console.timeEnd("handler #{label}")
    
  _rerunHandler: (handler, patch) ->
    handler.patterns = []
    @handlerStack.push(handler)
    try
      handler.func(patch)
    catch e
      log('error running handler: ', e)
      # assuming here it didn't get to do all its queries, we could
      # add a *,*,*,* handler to call for sure the next time?
    finally
      #log('done. got: ', handler.patterns)
      @handlerStack.pop()
    # handler might have no watches, in which case we could forget about it

  _logHandlerTree: ->
    log('handler tree:')
    prn = (h, depth) ->
      indent = ''
      for i in [0...depth]
        indent += '  '
      log(indent + h.label)
      for c in h.innerHandlers
        prn(c, depth + 1)
    prn(@handlers, 0)
    
  graphChanged: (patch) ->
    # SyncedGraph is telling us this patch just got applied to the graph.
    rerunInners = (cur) =>
      toRun = cur.innerHandlers.slice()
      for child in toRun

        #child.innerHandlers = [] # let all children get called again
        @_rerunHandler(child, patch)
        rerunInners(child)
    rerunInners(@handlers)

  askedFor: (s, p, o, g) ->
    # SyncedGraph is telling us someone did a query that depended on
    # quads in the given pattern.
    current = @handlerStack[@handlerStack.length - 1]
    if current? and current != @handlers
      current.patterns.push([s, p, o, g])
      #log('push', s,p,o,g)

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
    @_autoDeps = new AutoDependencies() # replaces GraphWatchers
    @clearGraph()

    if @patchSenderUrl
      @_client = new RdfDbClient(@patchSenderUrl, @_clearGraphOnNewConnection.bind(@),
                                 @_applyPatch.bind(@), @setStatus)
    
  clearGraph: ->
    # just deletes the statements; watchers are unaffected.
    if @graph?
      @_applyPatch({addQuads: [], delQuads: @graph.find()})

    # if we had a Store already, this lets N3.Store free all its indices/etc
    @graph = N3.Store()
    @_addPrefixes(@prefixes)
    @cachedFloatValues = new Map();

  _clearGraphOnNewConnection: -> # must not send a patch to the server!
    log('graph: clearGraphOnNewConnection')
    @clearGraph()
    log('graph: clearGraphOnNewConnection done')
      
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

  applyAndSendPatch: (patch) ->
    if !Array.isArray(patch.addQuads) || !Array.isArray(patch.delQuads)
      throw new Error("corrupt patch: #{patch}")

    for qs in [patch.addQuads, patch.delQuads]
      for q in qs
        if not q.graph?
          throw new Error("corrupt patch: #{q}")

    @_applyPatch(patch)
    @_client.sendPatch(patch) if @_client

  _applyPatch: (patch) ->
    # In most cases you want applyAndSendPatch.
    # 
    # This is the only method that writes to @graph!
    @cachedFloatValues.clear()
    for quad in patch.delQuads
      @graph.removeTriple(quad)
    for quad in patch.addQuads
      @graph.addTriple(quad)
    #log('applied patch locally', patchSizeSummary(patch))
    @_autoDeps.graphChanged(patch)

  getObjectPatch: (s, p, newObject, g) ->
    # make a patch which removes existing values for (s,p,*,c) and
    # adds (s,p,newObject,c). Values in other graphs are not affected.
    existing = @graph.findByIRI(s, p, null, g)
    return {
      delQuads: existing,
      addQuads: [{subject: s, predicate: p, object: newObject, graph: g}]
    }

  patchObject: (s, p, newObject, g) ->
    @applyAndSendPatch(@getObjectPatch(s, p, newObject, g))
  
  runHandler: (func, label) ->
    # runs your func once, tracking graph calls. if a future patch
    # matches what you queried, we runHandler your func again (and
    # forget your queries from the first time).

    # helps with memleak? not sure yet. The point was if two matching
    # labels get puushed on, we should run only one. So maybe
    # appending a serial number is backwards.
    @serial = 1 if not @serial
    @serial += 1
    #label = label + @serial
    
    @_autoDeps.runHandler(func, label)

  _singleValue: (s, p) ->
    @_autoDeps.askedFor(s, p, null, null)
    quads = @graph.findByIRI(s, p)
    objs = new Set(q.object for q in quads)
    
    switch objs.size
      when 0
        throw new Error("no value for "+s+" "+p)
      when 1
        obj = objs.values().next().value
        return obj
      else
        throw new Error("too many different values: " + JSON.stringify(quads))

  floatValue: (s, p) ->
    key = s + '|' + p
    hit = @cachedFloatValues.get(key)
    return hit if hit != undefined
    #log('float miss', s, p)

    ret = parseFloat(N3.Util.getLiteralValue(@_singleValue(s, p)))
    @cachedFloatValues.set(key, ret)
    return ret
    
  stringValue: (s, p) ->
    N3.Util.getLiteralValue(@_singleValue(s, p))
    
  uriValue: (s, p) ->
    @_singleValue(s, p)

  labelOrTail: (uri) ->
    try
      @graph.stringValue(uri, @graph.Uri('rdfs:label'))
    catch
      words = uri.split('/')
      words[words.length-1]

  objects: (s, p) ->
    @_autoDeps.askedFor(s, p, null, null)
    quads = @graph.findByIRI(s, p)
    return (q.object for q in quads)

  subjects: (p, o) ->
    @_autoDeps.askedFor(null, p, o, null)
    quads = @graph.findByIRI(null, p, o)
    return (q.subject for q in quads)

  items: (list) ->
    out = []
    current = list
    while true
      if current == RDF + 'nil'
        break
        
      firsts = @graph.findByIRI(current, RDF + 'first', null)
      rests = @graph.findByIRI(current, RDF + 'rest', null)
      if firsts.length != 1
        throw new Error("list node #{current} has #{firsts.length} rdf:first edges")
      out.push(firsts[0].object)

      if rests.length != 1
        throw new Error("list node #{current} has #{rests.length} rdf:rest edges")
      current = rests[0].object
    
    return out

  contains: (s, p, o) ->
    @_autoDeps.askedFor(s, p, o, null)
    return @graph.findByIRI(s, p, o).length > 0

  nextNumberedResources: (base, howMany) ->
    results = []
    # we could cache [base,lastSerial]
    for serial in [0..1000]
      uri = @Uri("#{base}#{serial}")
      if not @contains(uri, null, null)
        results.push(uri)
        if results.length >= howMany
          return results
    throw new Error("can't make sequential uri with base #{base}")

  nextNumberedResource: (base) ->
    @nextNumberedResources(base, 1)[0]       

  contextsWithPattern: (s, p, o) ->
    ctxs = []
    for q in @graph.find(s, p, o)
      ctxs.push(q.graph)
    return _.unique(ctxs)

