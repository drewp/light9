
window.graph = new SyncedGraph('noServerYet', {
'': 'http://light9.bigasterisk.com/',
'xsd', 'http://www.w3.org/2001/XMLSchema#',
  })
  
window.graph.loadTrig("
@prefix : <http://light9.bigasterisk.com/> .
@prefix dev: <http://light9.bigasterisk.com/device/> .

<http://example.com/> {
  :demoResource :startTime 0.5 .
}
    ")

    
class Adjustable
  # 
  constructor: (@config) ->
    @center = @config.getTarget().add(@config.getSuggestedTargetOffset())
    @getValue = @config.getValue

      
Polymer
  is: 'light9-timeline-editor'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    viewState: { type: Object }
  ready: ->
    @viewState =
      zoomSpec:
        duration: 190
        t1: 102
        t2: 161
      cursor:
        t: 105

    @fullZoomX = d3.scale.linear().domain([0, @viewState.zoomSpec.duration]).range([0, @offsetWidth])

    animCursor = () => 
      @viewState.cursor.t = 130 + 20 * Math.sin(Date.now() / 2000)
      @$.dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                       @$.zoomed.$.time.offsetTop, @$.zoomed.$.time.offsetHeight,
                       @viewState.zoomSpec, @viewState.cursor)

      @set('viewState.zoomSpec.t1', 80 + 10 * Math.sin(Date.now() / 3000))
      
    setInterval(animCursor, 50)

    setTimeout(() =>
      @adjs = @persistDemo() #@makeZoomAdjs().concat(@persistDemo())
    , 3000)


  persistDemo: ->
    adj = new Adjustable({
      getValue: () => (graph.floatValue(
        graph.Uri(':demoResource'),
        graph.Uri(':startTime')))
      getTarget: () => $V([200, 300])
      getSuggestedTargetOffset: () => $V([-30, 0])
      })
    console.log(adj.config.getValue())

    return [adj]

  makeZoomAdjs: ->
    left = new Adjustable({
      getValue: () => (@viewState.zoomSpec.t1)
      getTarget: () => $V([@fullZoomX(@viewState.zoomSpec.t1), @$.audio.offsetTop + @$.audio.offsetHeight / 2])
      getSuggestedTargetOffset: () => $V([-30, 0])
      })

    right = new Adjustable({
      getValue: () => (@viewState.zoomSpec.t2)
      getTarget: () => $V([@fullZoomX(@viewState.zoomSpec.t2), @$.audio.offsetTop + @$.audio.offsetHeight / 2])
      getSuggestedTargetOffset: () => $V([30, 0])
      })
    return [left, right]


Polymer
  is: 'light9-timeline-adjuster'
  properties:
    adj:
      type: Object
      notify: true
    target:
      type: Object
      notify: true
    value:
      type: String
      computed: '_value(adj.value)'
    centerStyle:
      computed: '_centerStyle(adj.center)'
      
  _value: (adjValue) ->
    d3.format(".4g")(adjValue)
    
  _centerStyle: (center) ->
    {
      x: center.e(1)
      y: center.e(2)
    }
    
  ready: ->
    subj = graph.Uri(':demoResource')
    pred = graph.Uri(':startTime')
    ctx = graph.Uri('http://example.com/')
    graph.subscribe subj, pred, null, (patch) =>
      for q in patch.addQuads
        @set('adj.value', graph.toJs(q.object))
    
    drag = d3.behavior.drag()
    sel = d3.select(@$.label)
    sel.call(drag)
    drag.origin((d) -> {x: @offsetLeft, y: @offsetTop})
    drag.on 'dragstart', () =>
      drag._startValue = @adj.getValue()

    drag.on 'drag', () =>
      console.log('drag', d3.event)
      newValue = drag._startValue + d3.event.x * .1
      graph.patchObject(subj, pred, graph.Literal(newValue), ctx)
