assert = require('chai').assert
SyncedGraph = require('./graph.js').SyncedGraph

describe 'SyncedGraph', ->
  describe 'constructor', ->
    it 'should successfully make an empty graph without connecting to rdfdb', ->
      g = new SyncedGraph()
      g.quads()
      assert.equal(g.quads().length, 0)

