# Patch is {addQuads: <quads>, delQuads: <quads>}
# <quads> is [{subject: s, ...}, ...]

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
    
  graphChanged: (patch) ->
    for quad in patch.delQuads
      for cb in ((@handlersSp[quad.subject] || {})[quad.predicate] || [])
        # currently calls multiple times, which is ok, but we might
        # group things into fewer patches
        cb({delQuads: [quad], addQuads: []})
    for quad in patch.addQuads
      for cb in ((@handlersSp[quad.subject] || {})[quad.predicate] || [])
        cb({delQuads: [], addQuads: [quad]})


class window.SyncedGraph
  # Note that applyPatch is the only method to write to the graph, so
  # it can fire subscriptions.

  constructor: (patchSenderUrl, prefixes) ->
    @graph = N3.Store()
    @_addPrefixes(prefixes)
    @_watchers = new GraphWatchers()

  _addPrefixes: (prefixes) ->
    @graph.addPrefixes(prefixes)
        
  Uri: (curie) ->
    N3.Util.expandPrefixedName(curie, @graph._prefixes)

  Literal: (jsValue) ->
    N3.Util.createLiteral(jsValue)

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
                    @applyPatch(patch)
                    @_addPrefixes(prefixes)
                    cb() if cb
                    
  quads: () -> # for debugging
    [q.subject, q.predicate, q.object, q.graph] for q in @graph.find()

  applyAndSendPatch: (patch, cb) ->
    @applyPatch(patch)
    #console.log('patch to server:')
    #console.log('  delete:', JSON.stringify(patch.delQuads))
    #console.log('  add:', JSON.stringify(patch.addQuads))
    # post to server

  applyPatch: (patch) ->
    # In most cases you want applyAndSendPatch.
    # 
    # This is the only method that writes to the graph!
    for quad in patch.delQuads
      @graph.removeTriple(quad)
    for quad in patch.addQuads
      @graph.addTriple(quad)
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

  floatValue: (s, p) ->
    quads = @graph.findByIRI(s, p)
    switch quads.length
      when 0 then throw new Error("no value for "+s+" "+p)
      when 1
        obj = quads[0].object
        return parseFloat(N3.Util.getLiteralValue(obj))
      else
        throw new Error("too many values: " + JSON.stringify(quads))
    
  stringValue: (s, p) ->

  uriValue: (s, p) ->

  objects: (s, p) ->

  subjects: (p, o) ->

  items: (list) ->

  contains: (s, p, o) ->

###
rdfstore.create((err, store) ->
  window.store = store
  store.setPrefix('l9', "http://light9.bigasterisk.com/")
  store.setPrefix('xsd', "http://www.w3.org/2001/XMLSchema#")
  store.load('text/turtle', "
@prefix : <http://light9.bigasterisk.com/> .
@prefix dev: <http://light9.bigasterisk.com/device/> .

:demoResource :startTime 0.5 .
    ", (err, n) ->
      console.log('loaded', n)
      store.graph (err, graph) ->
        window.graph = graph
        
    )
  window.URI = (curie) -> store.rdf.createNamedNode(store.rdf.resolve(curie))
  window.Lit = (value, dtype) -> store.rdf.createLiteral(value, null, URI(dtype))

  )
###