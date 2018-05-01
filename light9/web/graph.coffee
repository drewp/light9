log = console.log

# Patch is {addQuads: <quads>, delQuads: <quads>}
# <quads> are made with Quad(s,p,o,g)

# for mocha
if require?
  `window = {}`
  `_ = require('./lib/underscore/underscore-min.js')`
  `N3 = require('../../node_modules/n3/n3-browser.js')`
  `d3 = require('../../node_modules/d3/dist/d3.min.js')`
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
    #@_logHandlerTree()
    
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
      log("#{indent} \"#{h.label}\" #{h.patterns.length} pats")
      for c in h.innerHandlers
        prn(c, depth + 1)
    prn(@handlers, 0)

  _allPatchSubjs: (patch) ->

    allPatchSubjs = []
    for stmt in patch.addQuads
      allPatchSubjs.push(stmt.subject)
    for stmt in patch.delQuads
      allPatchSubjs.push(stmt.subject)
    allPatchSubjs = _.uniq(allPatchSubjs)
    if _.contains(allPatchSubjs, null) or allPatchSubjs.length == 0
      allPatchSubjs = null
    log('allPatchSubjs', allPatchSubjs)
    
  _handlerIsAffected: (child, allPatchSubjs) ->
    if allPatchSubjs == null
      return true
    if not child.patterns.length
      return false
      
    for stmt in child.patterns
      if _.contains(allPatchSubjs, stmt[0])
        return true

    return false
            
  graphChanged: (patch) ->
    # SyncedGraph is telling us this patch just got applied to the graph.

    #allPatchSubjs = @_allPatchSubjs(patch)
    
    rerunInners = (cur) =>
      toRun = cur.innerHandlers.slice()
      for child in toRun
        #match = @_handlerIsAffected(child, allPatchSubjs)
        #log('match', child.label, match)
        #child.innerHandlers = [] # let all children get called again
        
        @_rerunHandler(child, patch)
        rerunInners(child)
    rerunInners(@handlers)

  askedFor: (s, p, o, g) ->
    return
    # SyncedGraph is telling us someone did a query that depended on
    # quads in the given pattern.
    current = @handlerStack[@handlerStack.length - 1]
    if current? and current != @handlers
      current.patterns.push([s, p, o, g])
      #log('push', s,p,o,g)
    #else
    #  console.trace('read outside runHandler')

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
      @_applyPatch({addQuads: [], delQuads: @graph.getQuads()})

    # if we had a Store already, this lets N3.Store free all its indices/etc
    @graph = N3.Store()
    @_addPrefixes(@prefixes)
    @cachedFloatValues = new Map();

  _clearGraphOnNewConnection: -> # must not send a patch to the server!
    log('graph: clearGraphOnNewConnection')
    @clearGraph()
    log('graph: clearGraphOnNewConnection done')
      
  _addPrefixes: (prefixes) ->
    for k in (prefixes or {})
      @prefixes[k] = prefixes[k]
    @prefixFuncs = N3.Util.prefixes(@prefixes)
        
  Uri: (curie) ->
    if curie.match(/^http/)
      return N3.DataFactory.namedNode(curie)
    part = curie.split(':')
    return @prefixFuncs(part[0])(part[1])

  Literal: (jsValue) ->
    N3.DataFactory.literal(jsValue)

  LiteralRoundedFloat: (f) ->
    N3.DataFactory.literal(d3.format(".3f")(f),
                          "http://www.w3.org/2001/XMLSchema#double")

  Quad: (s, p, o, g) -> N3.DataFactory.quad(s, p, o, g)

  toJs: (literal) ->
    # incomplete
    parseFloat(literal.value)

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
    [q.subject, q.predicate, q.object, q.graph] for q in @graph.getQuads()

  applyAndSendPatch: (patch) ->
    console.time('applyAndSendPatch')
    if !Array.isArray(patch.addQuads) || !Array.isArray(patch.delQuads)
      throw new Error("corrupt patch: #{JSON.stringify(patch)}")

    @_validatePatch(patch)

    @_applyPatch(patch)
    @_client.sendPatch(patch) if @_client
    console.timeEnd('applyAndSendPatch')

  _validatePatch: (patch) ->
    for qs in [patch.addQuads, patch.delQuads]
      for q in qs
        if not q.equals
          throw new Error("doesn't look like a proper Quad")
        if not q.graph?
          throw new Error("corrupt patch: #{JSON.stringify(q)}")
    
  _applyPatch: (patch) ->
    # In most cases you want applyAndSendPatch.
    # 
    # This is the only method that writes to @graph!
    @cachedFloatValues.clear()
    for quad in patch.delQuads
      log("remove #{JSON.stringify(quad)}")      
      did = @graph.removeQuad(quad)
      log("removed: #{did}")
    for quad in patch.addQuads
      @graph.addQuad(quad)
    #log('applied patch locally', patchSizeSummary(patch))
    @_autoDeps.graphChanged(patch)

  getObjectPatch: (s, p, newObject, g) ->
    # make a patch which removes existing values for (s,p,*,c) and
    # adds (s,p,newObject,c). Values in other graphs are not affected.
    existing = @graph.getQuads(s, p, null, g)
    return {
      delQuads: existing,
      addQuads: [@Quad(s, p, newObject, g)]
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
    quads = @graph.getQuads(s, p)
    console.log('got',quads)
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

    ret = parseFloat(@_singleValue(s, p).value)
    @cachedFloatValues.set(key, ret)
    return ret
    
  stringValue: (s, p) ->
    @_singleValue(s, p).value
    
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
    quads = @graph.getQuads(s, p)
    return (q.object for q in quads)

  subjects: (p, o) ->
    @_autoDeps.askedFor(null, p, o, null)
    quads = @graph.getQuads(null, p, o)
    return (q.subject for q in quads)

  items: (list) ->
    out = []
    current = list
    while true
      if current == RDF + 'nil'
        break
        
      @_autoDeps.askedFor(current, null, null, null) # a little loose

      firsts = @graph.getQuads(current, RDF + 'first', null)
      rests = @graph.getQuads(current, RDF + 'rest', null)
      if firsts.length != 1
        throw new Error("list node #{current} has #{firsts.length} rdf:first edges")
      out.push(firsts[0].object)

      if rests.length != 1
        throw new Error("list node #{current} has #{rests.length} rdf:rest edges")
      current = rests[0].object
    
    return out

  contains: (s, p, o) ->
    @_autoDeps.askedFor(s, p, o, null)
    return @graph.getQuads(s, p, o).length > 0

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
    @_autoDeps.askedFor(s, p, o, null)
    ctxs = []
    for q in @graph.getQuads(s, p, o)
      ctxs.push(q.graph)
    return _.unique(ctxs)

