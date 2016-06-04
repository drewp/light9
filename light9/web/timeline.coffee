log = console.log

Polymer
  is: 'light9-timeline-editor'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    viewState: { type: Object }
    debug: {type: String}
    graph: {type: Object, notify: true}
  width: ko.observable(1)
  listeners:
    'iron-resize': '_onIronResize'
  _onIronResize: ->
    @width(@offsetWidth)

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
      @fullZoomX = d3.scaleLinear().domain([0, @viewState.zoomSpec.duration()]).range([0, @width()])
      @zoomInX = d3.scaleLinear().domain([@viewState.zoomSpec.t1(), @viewState.zoomSpec.t2()]).range([0, @width()])
      @$.adjusters.updateAllCoords()

    animCursor = () => 
      @viewState.cursor.t = 130 + 20 * Math.sin(Date.now() / 2000)
      @$.dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                       @$.zoomed.$.time.offsetTop,
                       @$.zoomed.$.time.offsetHeight,
                       @fullZoomX, @zoomInX, @viewState.cursor)

      #@viewState.zoomSpec.t1(80 + 10 * Math.sin(Date.now() / 3000))
      
    setInterval(animCursor, 50)

    @adjs = @makeZoomAdjs().concat(@persistDemo())


  persistDemo: ->
    ctx = @graph.Uri('http://example.com/')
    adjs = []
    for n in [0..7]
      subj = @graph.Uri(':demoResource'+n)
      adjs.push(new AdjustableFloatObject({
        graph: @graph
        subj: subj
        pred: @graph.Uri(':startTime')
        ctx: ctx
        getTargetTransform: (value) => $V([@zoomInX(value), 300])
        getValueForPos: (pos) => @zoomInX.invert(pos.e(1))
        getSuggestedTargetOffset: () => $V([-30, 80])
      }))
      adjs.push(new AdjustableFloatObject({
        graph: @graph
        subj: subj
        pred: @graph.Uri(':endTime')
        ctx: ctx
        getTargetTransform: (value) => $V([@zoomInX(value), 300])
        getValueForPos: (pos) => @zoomInX.invert(pos.e(1))
        getSuggestedTargetOffset: () => $V([30, 100])
      }))
    return adjs

  makeZoomAdjs: ->
    yMid = @$.audio.offsetTop + @$.audio.offsetHeight / 2
    dur = @viewState.zoomSpec.duration
    
    valForPos = (pos) =>
        x = pos.e(1)
        t = @fullZoomX.invert(x)
    left = new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t1,
      getTarget: () =>
        $V([@fullZoomX(@viewState.zoomSpec.t1()), yMid])
      getSuggestedTargetOffset: () => $V([-50, 0])
      getValueForPos: valForPos
    })

    right = new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t2,
      getTarget: () =>
        $V([@fullZoomX(@viewState.zoomSpec.t2()), yMid])
      getSuggestedTargetOffset: () => $V([50, 0])
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
      # fullzoom is not right- the sides shouldn't be able to go
      # offscreen
      getTarget: () => $V([@fullZoomX(panObs()), yMid])
      getSuggestedTargetOffset: () => $V([0, 0])
      getValueForPos: valForPos
      })
      
    return [left, right, pan]

Polymer
  is: "light9-timeline-adjusters"
  properties:
    adjs: { type: Array },
    dia: { type: Object }
  updateAllCoords: ->
    for elem in @querySelectorAll('light9-timeline-adjuster')
      elem.updateDisplay()
    

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
    @adj.subscribe(@updateDisplay.bind(this))

  updateDisplay: () ->
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
    @elemById = {}
    window.setNote = @setNote.bind(this)
    window.setMouse = @setMouse.bind(this)

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
    @cursorPath =
      top: @querySelector('#cursor1')
      mid: @querySelector('#cursor2')
      bot: @querySelector('#cursor3')
    return if !@cursorPath.top
    
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
