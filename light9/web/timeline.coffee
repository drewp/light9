log = console.log
window.graph = new SyncedGraph('noServerYet', {
'': 'http://light9.bigasterisk.com/',
'xsd', 'http://www.w3.org/2001/XMLSchema#',
  })
  
window.graph.loadTrig("
@prefix : <http://light9.bigasterisk.com/> .
@prefix dev: <http://light9.bigasterisk.com/device/> .

<http://example.com/> {
  :demoResource :startTime 110; :endTime 120 .
}
    ")

    
class Adjustable
  # Some value you can edit in the UI, probably by dragging stuff. May
  # have a <light9-timeline-adjuster> associated. This object does the
  # layout and positioning.
  constructor: (@config) ->
    # config has getTarget, getSuggestedTargetOffset, getValue, emptyBox

  getDisplayValue: () ->
    return '' if @config.emptyBox
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

class AdjustableFloatObservable extends Adjustable
  constructor: (@config) ->
    # config has observable, getValueForPos, valueLow, targetLow, valueHigh, targetHigh, getSuggestedTargetOffset
    ko.computed =>
      @_normalizedValue = d3.scaleLinear().domain([
        ko.unwrap(@config.valueLow),
        ko.unwrap(@config.valueHigh)]).range([0, 1])

  _getValue: () ->
    @config.observable()

  getTarget: () ->
    f = @_normalizedValue(@_getValue())
    [lo, hi] = [ko.unwrap(@config.targetLow),
                ko.unwrap(@config.targetHigh)]
    return lo.add(hi.subtract(lo).multiply(f))

  _editorCoordinates: () -> # vec2 of mouse relative to <l9-t-editor>
    ev = d3.event.sourceEvent

    if ev.target.tagName == "LIGHT9-TIMELINE-EDITOR"
      rootElem = ev.target
    else
      rootElem = ev.target.closest('light9-timeline-editor')
    
    @root = rootElem.getBoundingClientRect() if rootElem
    offsetParentPos = $V([ev.pageX - @root.left, ev.pageY - @root.top])

    setMouse(offsetParentPos)
    return offsetParentPos 
    
  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start.

    epos = @_editorCoordinates()
    log('offsetParentPos', epos.elements)
    
    newValue = @config.getValueForPos(epos)
    @config.observable(newValue)

  subscribe: (onChange) ->
    ko.computed =>
      @config.observable()
      onChange()

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
    debug: {type: String}
    
  attached: ->
    @dia = @$.dia
    @viewState =
      zoomSpec:
        duration: ko.observable(190)
        t1: ko.observable(102)
        t2: ko.observable(161)
      cursor:
        t: ko.observable(105)

    ko.computed =>
      @debug = ko.toJSON(@viewState)

    ko.computed =>
      @fullZoomX = d3.scaleLinear().domain([0, @viewState.zoomSpec.duration()]).range([0, @offsetWidth]) # need to update this if width changes or if duration changes
      @zoomInX = d3.scaleLinear().domain([@viewState.zoomSpec.t1(), @viewState.zoomSpec.t2()]).range([0, @offsetWidth]) # need to update this if width changes or if duration changes

    animCursor = () => 
      #@viewState.cursor.t = 130 + 20 * Math.sin(Date.now() / 2000)
      @$.dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                       @$.zoomed.$.time.offsetTop,
                       @$.zoomed.$.time.offsetHeight,
                       @fullZoomX, @zoomInX, @viewState.cursor)

      @viewState.zoomSpec.t1(80 + 10 * Math.sin(Date.now() / 3000))
      
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
        getSuggestedTargetOffset: () => $V([-30, 80])
      })
      new AdjustableFloatObject({
        graph: graph
        subj: graph.Uri(':demoResource')
        pred: graph.Uri(':endTime')
        ctx: ctx
        getTarget: () => $V([300, 300])
        getSuggestedTargetOffset: () => $V([30, 100])
      })
      ]

  makeZoomAdjs: ->
    dur = @viewState.zoomSpec.duration
    valForPos = (pos) =>
        x = pos.e(1)
        t = @fullZoomX.invert(x)
    left = new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t1,
      valueLow: 0
      valueHigh: dur
      targetLow: $V([0, 30])  # y = @$.audio.offsetTop + @$.audio.offsetHeight / 2]
      targetHigh: $V([@offsetWidth, 30])
      getSuggestedTargetOffset: () => $V([-30, 0])
      getValueForPos: valForPos
    })

    right = new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t2,
      valueLow: 0
      valueHigh: dur
      targetLow: $V([0, 30])  # y = @$.audio.offsetTop + @$.audio.offsetHeight / 2]
      targetHigh: $V([@offsetWidth, 30])
      getSuggestedTargetOffset: () => $V([30, 0])
      getValueForPos: valForPos
    })

    panObs = ko.pureComputed({
        read: () =>
          (@viewState.zoomSpec.t1() + @viewState.zoomSpec.t2()) / 2
        write: (value) =>
          zs = @viewState.zoomSpec
          span = zs.t2() - zs.t1()
          zs.t1(value - span / 2)
          zs.t2(value + span / 2)
      })

    pan = new AdjustableFloatObservable({
      observable: panObs
      emptyBox: true
      valueLow: 0
      valueHigh: dur
      # not right- the sides shouldn't be able to go offscreen
      targetLow: $V([0, 30])  # y = @$.audio.offsetTop + @$.audio.offsetHeight / 2]
      targetHigh: $V([@offsetWidth, 30])
      getSuggestedTargetOffset: () => $V([0, 0])
      getValueForPos: valForPos
      })
      
    return [left, right, pan]

_adjusterSerial = 0

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
    spanClass:
      type: String
      value: ''

  onAdj: (adj) ->
    @adj.subscribe () =>
      @spanClass = if @adj.config.emptyBox then 'empty' else ''
      @displayValue = @adj.getDisplayValue()
      center = @adj.getCenter()
      @centerStyle = {x: center.e(1), y: center.e(2)}
      @dia?.setAdjusterConnector(@myId, @adj.getCenter(),
                                @adj.getTarget())
        
  attached: ->
    @myId = 'adjuster-' + _adjusterSerial
    _adjusterSerial += 1
    
    drag = d3.drag()
    sel = d3.select(@$.label)
    sel.call(drag)
    drag.subject((d) -> {x: @offsetLeft, y: @offsetTop})
    drag.container(@offsetParent)
    drag.on('start', () => @adj?.startDrag())
    drag.on 'drag', () =>
      @adj?.continueDrag($V([d3.event.x, d3.event.y]))
    drag.on('end', () => @adj?.endDrag())


svgPathFromPoints = (pts) ->
  out = ''
  pts.forEach (p) ->
    p = p.elements if p.elements # for vec2
    if out.length == 0
      out = 'M '
    else
      out += 'L '
    out += '' + p[0] + ',' + p[1] + ' '
    return
  out

Polymer
  is: 'light9-timeline-diagram-layer'
  properties: {}
  ready: ->
    window.setNote = @setNote.bind(this)
    window.setMouse = @setMouse.bind(this)
    @cursorPath =
      top: @querySelector('#cursor1')
      mid: @querySelector('#cursor2')
      bot: @querySelector('#cursor3')
    @elemById = {}

  setMouse: (pos) ->
    elem = @getOrCreateElem('mouse-x', 'mouse', 'path', {style: "fill:none;stroke:#333;stroke-width:0.5;"})
    elem.setAttribute('d', svgPathFromPoints([[-999, pos.e(2)], [999, pos.e(2)]]))
    elem = @getOrCreateElem('mouse-y', 'mouse', 'path', {style: "fill:none;stroke:#333;stroke-width:0.5;"})
    elem.setAttribute('d', svgPathFromPoints([[pos.e(1), -999], [pos.e(1), 999]]))
    

  getOrCreateElem: (uri, groupId, tag, attrs) ->
    elem = @elemById[uri]
    if !elem
      elem = @elemById[uri] = document.createElementNS("http://www.w3.org/2000/svg", tag)
      @$[groupId].appendChild(elem)
      elem.setAttribute('id', uri)
      for k,v of attrs
        elem.setAttribute(k, v)
    return elem
    
  setNote: (uri, x1, x2, y1, y2) ->
    elem = @getOrCreateElem(uri, 'notes', 'path', {style:"fill:#53774b; stroke:#000000; stroke-width:1.5;"})
    d = svgPathFromPoints([
      [x1, y2]
      [x1 * .75 + x2 * .25, y1]
      [x1 * .25 + x2 * .75, y1]
      [x2, y2]
    ])
    elem.setAttribute('d', d)

  setCursor: (y1, h1, y2, h2, fullZoomX, zoomInX, cursor) ->
    xZoomedOut = fullZoomX(cursor.t)
    xZoomedIn = zoomInX(cursor.t)
    @cursorPath.top.setAttribute 'd', svgPathFromPoints([
      [xZoomedOut, y1]
      [xZoomedOut, y1 + h1]
    ])
    @cursorPath.mid.setAttribute 'd', svgPathFromPoints([
      [xZoomedIn + 2, y2 + h2]
      [xZoomedIn - 2, y2 + h2]
      [xZoomedOut - 1, y1 + h1]
      [xZoomedOut + 1, y1 + h1]
    ]) + ' Z'
    @cursorPath.bot.setAttribute 'd', svgPathFromPoints([
      [xZoomedIn, y2 + h2]
      [xZoomedIn, @offsetParent.offsetHeight]
    ])

  setAdjusterConnector: (uri, center, target) ->
    elem = @getOrCreateElem(uri, 'connectors', 'path', {style: "fill:none;stroke:#d4d4d4;stroke-width:0.9282527;stroke-linecap:butt;stroke-linejoin:miter;stroke-miterlimit:4;stroke-dasharray:2.78475821, 2.78475821;stroke-dashoffset:0;"})
    elem.setAttribute('d', svgPathFromPoints([center, target]))
