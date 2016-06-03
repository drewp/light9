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
    # config has getTarget, getSuggestedTargetOffset, getValue

  getDisplayValue: () ->
    d3.format(".4g")(@_getValue())

  getCenter: () -> # vec2 of pixels
    @getTarget().add(@config.getSuggestedTargetOffset())

  getTarget: () -> # vec2 of pixels
    @config.getTarget()
            
  subscribe: (onChange) ->
    # change could be displayValue or center or target. This likely
    # calls onChange right away if there's any data yet.
    setInterval((() => onChange()), 100)

  startDrag: () ->
    # todo
    @dragStartValue = @_getValue()

  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start
    
    # todo
    newValue = @dragStartValue + pos.e(0) * .1
    graph.patchObject(@_subj, @_pred, graph.Literal(newValue), @_ctx)

  endDrag: () ->
    0

class AdjustableFloatJsValue extends Adjustable
  constructor: (@config) ->
    # config has obj, key, valueLow, targetLow, valueHigh, targetHigh, getSuggestedTargetOffset, onChange
    @_normalizedValue = d3.scaleLinear().domain([@config.valueLow, @config.valueHigh]).range([0, 1])

  _getValue: () ->
    @config.obj[@config.key]

  getTarget: () ->
    f = @_normalizedValue(@_getValue())
    [l, h] = [@config.targetLow, @config.targetHigh]
    return l.add(h.subtract(l).multiply(f))
    
  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start
    
    # todo
    newValue = @dragStartValue + pos.e(1) * .1
    @config.obj[@config.key] = newValue
    @config.onChange()


class AdjustableFloatObject extends Adjustable
  constructor: (@config) ->
    # config has graph, subj, pred, ctx, getSuggestedTargetOffset
    super(@config)

  _getValue: () -> # for drag math
    @config.graph.floatValue(@config.subj, @config.pred)

  getCenter: () ->    
    $V([100 + 200 * @_getValue(), 200])

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
    debug: {type: String, computed: '_debug(viewState.zoomSpec.t1)'}
  _debug: (viewState) ->
    JSON.stringify(@viewState)
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
      #@viewState.cursor.t = 130 + 20 * Math.sin(Date.now() / 2000)
      @$.dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                       @$.zoomed.$.time.offsetTop,
                       @$.zoomed.$.time.offsetHeight,
                       @fullZoomX, @zoomInX, @viewState.cursor)

      @set('viewState.zoomSpec.t1', 80 + 10 * Math.sin(Date.now() / 3000))
      
    #setInterval(animCursor, 50)

    setTimeout(() =>
      @adjs = @makeZoomAdjs().concat(@persistDemo())
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
    
    left = new AdjustableFloatJsValue({
      obj: @viewState.zoomSpec,
      key: 't1'
      valueLow: 0
      valueHigh: @viewState.zoomSpec.duration
      targetLow: $V([0, 30])  # y = @$.audio.offsetTop + @$.audio.offsetHeight / 2]
      targetHigh: $V([@offsetWidth, 30])
      getSuggestedTargetOffset: () => $V([-30, 0])
      onChange: () => @notifyPath('viewState.zoomSpec.t1', @viewState.zoomSpec.t1)
    })

    right = new AdjustableFloatJsValue({
      obj: @viewState.zoomSpec,
      key: 't2'
      valueLow: 0
      valueHigh: @viewState.zoomSpec.duration
      targetLow: $V([0, 30])  # y = @$.audio.offsetTop + @$.audio.offsetHeight / 2]
      targetHigh: $V([@offsetWidth, 30])
      getSuggestedTargetOffset: () => $V([30, 0])
      onChange: () => @notifyPath('viewState.zoomSpec.t2', @viewState.zoomSpec.t2)
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
  