log = console.log
assert = require('chai').assert
expect = require('chai').expect
SyncedGraph = require('./graph.js').SyncedGraph

describe 'SyncedGraph', ->
  describe 'constructor', ->
    it 'should successfully make an empty graph without connecting to rdfdb', ->
      g = new SyncedGraph()
      g.quads()
      assert.equal(g.quads().length, 0)

  describe 'auto dependencies', ->
    graph = new SyncedGraph()
    RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
    U = (tail) -> graph.Uri('http://example.com/' + tail)
    A1 = U('a1')
    A2 = U('a2')
    A3 = U('a3')
    A4 = U('a4')
    ctx = U('ctx')
    quad = (s, p, o) -> graph.Quad(s, p, o, ctx)

    beforeEach (done) ->
      graph = new SyncedGraph()
      graph.loadTrig("
        @prefix : <http://example.com/> .
        :ctx {
          :a1 :a2 :a3 .
          :a1 :someFloat 1.5 .
          :a1 :someString \"hello\" .
          :a1 :multipleObjects :a4, :a5 .
          :a2 a :Type1 .
          :a3 a :Type1 .
        }
      ", done)
    
    it 'calls a handler right away', ->
      called = 0
      hand = ->
        called++
      graph.runHandler(hand, 'run')
      assert.equal(1, called)
      
    it 'calls a handler a 2nd time if the graph is patched with relevant data', ->
      called = 0
      hand = ->
        called++
        graph.uriValue(A1, A2)
      graph.runHandler(hand, 'run')
      graph.applyAndSendPatch({
        delQuads: [quad(A1, A2, A3)], addQuads: [quad(A1, A2, A4)]})
      assert.equal(2, called) 

    it 'notices new queries a handler makes upon rerun', ->
      called = 0
      objsFound = []
      hand = ->
        called++
        graph.uriValue(A1, A2)
        if called > 1
          objsFound.push(graph.objects(A1, A3))
      graph.runHandler(hand, 'run')
      # first run looked up A1,A2,*
      graph.applyAndSendPatch({
        delQuads: [quad(A1, A2, A3)], addQuads: [quad(A1, A2, A4)]})
      # second run also looked up A1,A3,* (which matched none)
      graph.applyAndSendPatch({
        delQuads: [], addQuads: [quad(A1, A3, A4)]})
      # third run should happen here, noticing the new A1,A3,* match
      assert.equal(3, called)
      assert.deepEqual([[], [A4]], objsFound)

    it 'calls a handler again even if the handler throws an error', ->
      called = 0
      hand = ->
        called++
        graph.uriValue(A1, A2)
        throw new Error('this test handler throws an error')
      graph.runHandler(hand, 'run')
      graph.applyAndSendPatch({
        delQuads: [quad(A1, A2, A3)], addQuads: [quad(A1, A2, A4)]})
      assert.equal(2, called) 

    describe 'works with nested handlers', ->

      innerResults = []
      inner = ->
        console.log('\nninnerfetch')
        innerResults.push(graph.uriValue(A1, A2))
        console.log("innerResults #{JSON.stringify(innerResults)}\n")

      outerResults = []
      doRunInner = true
      outer = ->
        if doRunInner
          graph.runHandler(inner, 'runinner')
        console.log('push outer')
        outerResults.push(graph.floatValue(A1, U('someFloat')))

      beforeEach ->
        innerResults = []
        outerResults = []
        doRunInner = true

      affectInner = {
        delQuads: [quad(A1, A2, A3)], addQuads: [quad(A1, A2, A4)]
      }
      affectOuter = {
        delQuads: [
          quad(A1, U('someFloat'), graph.Literal(1.5))
        ], addQuads: [
          quad(A1, U('someFloat'), graph.LiteralRoundedFloat(2))
        ]}
      affectBoth = {
        delQuads: affectInner.delQuads.concat(affectOuter.delQuads),
        addQuads: affectInner.addQuads.concat(affectOuter.addQuads)
        }
                  
      it 'calls everything normally once', ->
        graph.runHandler(outer, 'run')
        assert.deepEqual([A3], innerResults)
        assert.deepEqual([1.5], outerResults)

      it.skip '[performance] reruns just the inner if its dependencies change', ->
        console.log(graph.quads())
        graph.runHandler(outer, 'run')
        graph.applyAndSendPatch(affectInner)
        assert.deepEqual([A3, A4], innerResults)
        assert.deepEqual([1.5], outerResults)
        
      it.skip '[performance] reruns the outer (and therefore inner) if its dependencies change', ->
        graph.runHandler(outer, 'run')
        graph.applyAndSendPatch(affectOuter)
        assert.deepEqual([A3, A3], innerResults)
        assert.deepEqual([1.5, 2], outerResults)
        
        
      it.skip '[performance] does not send a redundant inner run if it is already rerunning outer', ->
        # Note that outer may or may not call inner each time, and we
        # don't want to redundantly call inner. We need to:
        #  1. build the set of handlers to rerun,
        #  2. call them from outside-in, and
        #  3. any runHandler calls that happen, they need to count as reruns.
        graph.runHandler(outer, 'run')
        graph.applyAndSendPatch(affectBoth)
        assert.deepEqual([A3, A4], innerResults)
        assert.deepEqual([1.5, 2], outerResults)

      it 'reruns the outer and the inner if all dependencies change, but outer omits calling inner this time', ->
        graph.runHandler(outer, 'run')
        doRunInner = false
        graph.applyAndSendPatch(affectBoth)
        assert.deepEqual([A3, A4], innerResults)
        assert.deepEqual([1.5, 2], outerResults)
        
    describe 'watches calls to:', ->
      it 'floatValue', ->
        values = []
        hand = -> values.push(graph.floatValue(A1, U('someFloat')))
        graph.runHandler(hand, 'run')
        graph.patchObject(A1, U('someFloat'), graph.LiteralRoundedFloat(2), ctx)
        assert.deepEqual([1.5, 2.0], values)
        
      it 'stringValue', ->
        values = []
        hand = -> values.push(graph.stringValue(A1, U('someString')))
        graph.runHandler(hand, 'run')
        graph.patchObject(A1, U('someString'), graph.Literal('world'), ctx)
        assert.deepEqual(['hello', 'world'], values)

      it 'uriValue', ->
        # covered above, but this one tests patchObject on a uri, too
        values = []
        hand = -> values.push(graph.uriValue(A1, A2))
        graph.runHandler(hand, 'run')
        graph.patchObject(A1, A2, A4, ctx)
        assert.deepEqual([A3, A4], values)

      it 'objects', ->
        values = []
        hand = -> values.push(graph.objects(A1, U('multipleObjects')))
        graph.runHandler(hand, 'run')
        graph.patchObject(A1, U('multipleObjects'), U('newOne'), ctx)
        expect(values[0]).to.deep.have.members([U('a4'), U('a5')])
        expect(values[1]).to.deep.have.members([U('newOne')])

      it 'subjects', ->
        values = []
        rdfType = graph.Uri(RDF + 'type')
        hand = -> values.push(graph.subjects(rdfType, U('Type1')))
        graph.runHandler(hand, 'run')
        graph.applyAndSendPatch(
          {delQuads: [], addQuads: [quad(A4, rdfType, U('Type1'))]})
        expect(values[0]).to.deep.have.members([A2, A3])
        expect(values[1]).to.deep.have.members([A2, A3, A4])

      describe 'items', ->
        it 'when the list order changes', (done) ->
          values = []
          successes = 0
          hand = ->
            try 
              head = graph.uriValue(U('x'), U('y'))
            catch
              # graph goes empty between clearGraph and loadTrig
              return
            values.push(graph.items(head))
            successes++
          graph.clearGraph()
          graph.loadTrig "
            @prefix : <http://example.com/> .
            :ctx { :x :y (:a1 :a2 :a3) } .
          ", () ->
            graph.runHandler(hand, 'run')
            graph.clearGraph()
            graph.loadTrig "
              @prefix : <http://example.com/> .
              :ctx { :x :y (:a1 :a3 :a2) } .
            ", () ->
              assert.deepEqual([[A1, A2, A3], [A1, A3, A2]], values)
              assert.equal(2, successes)
              done()
  
      describe 'contains', ->
        it 'when a new triple is added', ->
          values = []
          hand = -> values.push(graph.contains(A1, A1, A1))
          graph.runHandler(hand, 'run')
          graph.applyAndSendPatch(
            {delQuads: [], addQuads: [quad(A1, A1, A1)]})
          assert.deepEqual([false, true], values)

        it 'when a relevant triple is removed', ->
          values = []
          hand = -> values.push(graph.contains(A1, A2, A3))
          graph.runHandler(hand, 'run')
          graph.applyAndSendPatch(
            {delQuads: [quad(A1, A2, A3)], addQuads: []})
          assert.deepEqual([true, false], values)

    describe 'performs well', ->
      it "[performance] doesn't call handler a 2nd time if the graph gets an unrelated patch", ->
        called = 0
        hand = ->
          called++
          graph.uriValue(A1, A2)
        graph.runHandler(hand, 'run')
        graph.applyAndSendPatch({
          delQuads: [], addQuads: [quad(A2, A3, A4)]})
        assert.equal(1, called)

      it.skip '[performance] calls a handler 2x but then not again if the handler stopped caring about the data', ->
        assert.fail()

      it.skip "[performance] doesn't get slow if the handler makes tons of repetitive lookups", ->
        assert.fail()
