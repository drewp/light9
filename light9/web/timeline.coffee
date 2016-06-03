log = console.log
window.graph = new SyncedGraph('noServerYet', {
'': 'http://light9.bigasterisk.com/',
'xsd', 'http://www.w3.org/2001/XMLSchema#',
  })
  
window.graph.loadTrig("
@prefix : <http://light9.bigasterisk.com/> .
@prefix dev: <http://light9.bigasterisk.com/device/> .

<http://example.com/> {
  :demoResource :startTime 0.5; :endTime 1.6 .
}
    ")

    
class Adjustable
  # Some value you can edit in the UI, probably by dragging stuff. May
  # have a <light9-timeline-adjuster> associated. This object does the
  # layout and positioning.
  constructor: (@config) ->
    @_center = @config.getTarget().add(@config.getSuggestedTargetOffset())

  getDisplayValue: () ->
    # todo
    d3.format(".4g")(@config.getValue())

  getCenter: () -> # vec2 of pixels
    @_center

  getTarget: () -> # vec2 of pixels
    @config.getTarget()
            
  subscribe: (onChange) ->
    # change could be displayValue or center or target. This likely
    # calls onChange right away if there's any data yet.
    

  startDrag: () ->
    # todo
    @dragStartValue = @getValue()

  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start
    
    # todo
    newValue = @dragStartValue + pos.e(0) * .1
    graph.patchObject(@_subj, @_pred, graph.Literal(newValue), @_ctx)

  endDrag: () ->
    0

class AdjustableFloatObject extends Adjustable
  constructor: (@config) ->
    # config has graph, subj, pred, ctx
    super(@config)

  getValue: () -> # for drag math
    @config.graph.floatValue(@config.subj, @config.pred)

  getCenter: () ->
    
    $V([100 + 200 * @getValue(), 200])

  getDisplayValue: () ->
    d3.format(".4g")(@getValue())

  subscribe: (onChange) ->
    @config.graph.subscribe @config.subj, @config.pred, null, (patch) =>
      onChange()
    
  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start
    
    newValue = @dragStartValue + pos.e(1) / 200
    @config.graph.patchObject(@config.subj, @config.pred, @config.graph.Literal(newValue), @_ctx)

      
Polymer
  is: 'light9-timeline-editor'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    viewState: { type: Object }
  attached: ->
    @viewState =
      zoomSpec:
        duration: 190
        t1: 102
        t2: 161
      cursor:
        t: 105

    @fullZoomX = d3.scaleLinear().domain([0, @viewState.zoomSpec.duration]).range([0, @offsetWidth]) # need to update this if width changes or if duration changes
    @zoomInX = d3.scaleLinear().domain([@viewState.zoomSpec.t1, @viewState.zoomSpec.t2]).range([0, @offsetWidth]) # need to update this if width changes or if duration changes


    animCursor = () => 
      @viewState.cursor.t = 130 + 20 * Math.sin(Date.now() / 2000)
      @$.dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                       @$.zoomed.$.time.offsetTop, @$.zoomed.$.time.offsetHeight,
                       @fullZoomX, @zoomInX, @viewState.cursor)

      @set('viewState.zoomSpec.t1', 80 + 10 * Math.sin(Date.now() / 3000))
      
    setInterval(animCursor, 50)

    setTimeout(() =>
      @adjs = @persistDemo()#@makeZoomAdjs().concat(@persistDemo())
    , 100)

  persistDemo: ->
    ctx = graph.Uri('http://example.com/')
    return [
      new AdjustableFloatObject({
        graph: graph
        subj: graph.Uri(':demoResource')
        pred: graph.Uri(':startTime')
        ctx: ctx
        getTarget: () => $V([200, 300])
        getSuggestedTargetOffset: () => $V([-30, 0])
      })
      new AdjustableFloatObject({
        graph: graph
        subj: graph.Uri(':demoResource')
        pred: graph.Uri(':endTime')
        ctx: ctx
        getTarget: () => $V([300, 300])
        getSuggestedTargetOffset: () => $V([30, 0])
      })
      ]

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
      observer: 'onAdj'
    target:
      type: Object
      notify: true
    displayValue:
      type: String
    centerStyle:
      type: Object
      
  onAdj: (adj) ->
    console.log('adj is here', adj, @adj)
    @adj.subscribe () =>
      @displayValue = @adj.getDisplayValue()
      center = @adj.getCenter()
      @centerStyle = {x: center.e(1), y: center.e(2)}
        
  attached: ->
    drag = d3.drag()
    sel = d3.select(@$.label)
    sel.call(drag)
    drag.subject((d) -> {x: @offsetLeft, y: @offsetTop})
    drag.container(@offsetParent)
    drag.on('start', () => @adj?.startDrag())
    drag.on 'drag', () =>
      @adj?.continueDrag($V([d3.event.x, d3.event.y]))
    drag.on('end', () => @adj?.endDrag())
  