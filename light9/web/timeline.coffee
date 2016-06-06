log = console.log

Polymer
  is: 'light9-timeline-editor'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    viewState: { type: Object }
    debug: {type: String}
    graph: {type: Object, notify: true}
    song: {type: String, notify: true}
    show: {value: 'http://light9.bigasterisk.com/show/dance2016'}
    songTime: {type: Number, notify: true, observer: '_onSongTime'}
    songDuration: {type: Number, notify: true, observer: '_onSongDuration'}
    songPlaying: {type: Boolean, notify: true}
  width: ko.observable(1)
  listeners:
    'iron-resize': '_onIronResize'
  _onIronResize: ->
    @width(@offsetWidth)
  _onSongTime: (t) ->
    @viewState.cursor.t(t)
  _onSongDuration: (d) ->
    @viewState.zoomSpec.duration(d)

  ready: ->
    @viewState =
      zoomSpec:
        duration: ko.observable(100)
        t1: ko.observable(0) # need validation to stay in bounds and not go too close
        t2: ko.observable(100)
      cursor:
        t: ko.observable(20)
      mouse:
        pos: ko.observable($V([0,0]))
    
  attached: ->
    @dia = @$.dia

    ko.computed =>
      @debug = ko.toJSON(@viewState)

    ko.computed( =>
        @fullZoomX = d3.scaleLinear().domain([0, @viewState.zoomSpec.duration()]).range([0, @width()])
        @zoomInX = d3.scaleLinear().domain([@viewState.zoomSpec.t1(), @viewState.zoomSpec.t2()]).range([0, @width()])
        @dia.setTimeAxis(@width(), @$.zoomed.$.audio.offsetTop, @zoomInX)
        @$.adjusters.updateAllCoords()
      ).extend({rateLimit: 5})

    ko.computed( =>
        # zoomInX changing doesn't retrigger this, so I'll do it here
        ko.toJS(@viewState.zoomSpec)
        
        @$.dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                         @$.zoomed.$.time.offsetTop,
                         @$.zoomed.$.time.offsetHeight,
                         @fullZoomX, @zoomInX, @viewState.cursor)
      )

    @adjs = @makeZoomAdjs()

    @trackMouse()
    @bindKeys()
    @bindWheelZoom()

  trackMouse: ->
    # not just for show- we use the mouse pos sometimes
    for evName in ['mousemove', 'touchmove']
      @addEventListener evName, (ev) =>
        ev.preventDefault()

        # todo: consolidate with _editorCoordinates version
        if ev.touches?.length
          ev = ev.touches[0]

        @root = @getBoundingClientRect()
        @viewState.mouse.pos($V([ev.pageX - @root.left, ev.pageY - @root.top]))

        @$.dia.setMouse(@viewState.mouse.pos())

  latestMouseTime: ->
    @zoomInX.invert(@viewState.mouse.pos().e(1))

  bindWheelZoom: ->
    @$.zoomed.addEventListener 'mousewheel', (ev) =>
      zs = @viewState.zoomSpec

      center = @latestMouseTime()
      left = center - zs.t1()
      right = zs.t2() - center
      scale = Math.pow(1.005, ev.deltaY)

      zs.t1(center - left * scale)
      zs.t2(center + right * scale)

  animatedZoom: (newT1, newT2, secs) ->
    fps = 30
    oldT1 = @viewState.zoomSpec.t1()
    oldT2 = @viewState.zoomSpec.t2()
    lastTime = 0
    for step in [0..secs * fps]
      frac = step / (secs * fps)
      do (frac) =>
        gotoStep = =>
          @viewState.zoomSpec.t1((1 - frac) * oldT1 + frac * newT1)
          @viewState.zoomSpec.t2((1 - frac) * oldT2 + frac * newT2)
        delay = frac * secs * 1000
        setTimeout(gotoStep, delay)
        lastTime = delay
    setTimeout(=>
        @viewState.zoomSpec.t1(newT1)
        @viewState.zoomSpec.t2(newT2)
      , lastTime + 10)  
    
  bindKeys: ->
    shortcut.add "Ctrl+P", (ev) =>
      @$.music.seekPlayOrPause(@latestMouseTime())

    zoomAnimSec = .1
    shortcut.add "Ctrl+Escape", =>
      @animatedZoom(0, @viewState.zoomSpec.duration(), zoomAnimSec)
    shortcut.add "Shift+Escape", =>
      @animatedZoom(@songTime - 2, @viewState.zoomSpec.duration(), zoomAnimSec)
    shortcut.add "Escape", =>
      zs = @viewState.zoomSpec
      visSeconds = zs.t2() - zs.t1()
      margin = visSeconds * .4
      # buggy: really needs t1/t2 to limit their ranges
      if @songTime < zs.t1() or @songTime > zs.t2() - visSeconds * .6
        newCenter = @songTime + margin
        @animatedZoom(newCenter - visSeconds / 2,
                      newCenter + visSeconds / 2, zoomAnimSec)

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
  is: "light9-timeline-time-axis",
  # for now since it's just one line calling dia,
  # light9-timeline-editor does our drawing work.

Polymer
  is: 'light9-timeline-graph-row'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    graph: { type: Object, notify: true }
    zoomInX: { type: Object, notify: true }
    noteUris: { type: Array, notify: true }
    rowIndex: { type: Object, notify: true }
  observers: [
    'onGraph(graph, zoomInX)'
    ]
  onGraph: ->
    @graph.runHandler(@update.bind(@))
  update: ->
    U = (x) -> @graph.Uri(x)

    @noteUris = []
    for note in @graph.objects(@song, U(':note'))
      @push('noteUris', note)
  

Polymer
  is: 'light9-timeline-note'
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'update'
  properties:
    graph: { type: Object, notify: true }
    uri: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
  observers: [
    'onUri(graph, uri)'
    'update(graph, uri, zoomInX)'
    ]
  ready: ->

  onUri: ->
    @graph.runHandler(@update.bind(@))
    
  update: ->
    # update our note DOM and SVG elements based on the graph
    U = (x) -> @graph.Uri(x)
    try
      worldPts = [] # (song time, value)

      originTime = @graph.floatValue(@uri, U(':originTime'))
      for curve in @graph.objects(@uri, U(':curve'))
        if @graph.uriValue(curve, U(':attr')) == U(':strength')
          
          for pt in @graph.objects(curve, U(':point'))

            worldPts.push($V([
              originTime + @graph.floatValue(pt, U(':time')),
              @graph.floatValue(pt, U(':value'))
              ]))
      worldPts.sort((a,b) -> a.e(1) > b.e(1))

      screenPos = (pt) =>
        $V([@zoomInX(pt.e(1)), @offsetTop + (1 - pt.e(2)) * @offsetHeight])

      setNote(@uri, (screenPos(pt) for pt in worldPts))

    catch e
      log("during resize of #{@uri}: #{@e}")

Polymer
  is: "light9-timeline-adjusters"
  properties:
    adjs: { type: Array }, # our computed list
    parentAdjs: { type: Array }, # incoming requests
    graph: { type: Object, notify: true }
    song: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
    dia: { type: Object }
  observers: [
    'update(parentAdjs, graph, song, dia)'
    'onGraph(graph, song)'
    ]
  onGraph: (graph, song, zoomInX) ->
    graph.runHandler(@update.bind(@))
  update: (parentAdjs, graph, song, dia) ->
    U = (x) -> @graph.Uri(x)
    @adjs = (@parentAdjs || []).slice()
    for note in @graph.objects(@song, U(':note'))
      @push('adjs', new AdjustableFloatObject({
        graph: @graph
        subj: note
        pred: @graph.Uri(':originTime')
        ctx: @graph.Uri(@song)
        getTargetTransform: (value) => $V([@zoomInX(value), 600])
        getValueForPos: (pos) => @zoomInX.invert(pos.e(1))
        getSuggestedTargetOffset: () => $V([0, -80])
      }))
    
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
      target = @adj.getTarget()
      return if isNaN(center.e(1))
      @centerStyle = {x: center.e(1), y: center.e(2)}
      @dia?.setAdjusterConnector(@myId, center, target)
        
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

  setTimeAxis: (width, yTop, scale) ->
    pxPerTick = 50
    axis = d3.axisTop(scale).ticks(width / pxPerTick)
    d3.select(@$.timeAxis).attr('transform', 'translate(0,'+yTop+')').call(axis)

  setMouse: (pos) ->
    elem = @getOrCreateElem('mouse-x', 'mouse', 'path', {style: "fill:none;stroke:#fff;stroke-width:0.5;"})
    elem.setAttribute('d', svgPathFromPoints([[-9999, pos.e(2)], [9999, pos.e(2)]]))
    elem = @getOrCreateElem('mouse-y', 'mouse', 'path', {style: "fill:none;stroke:#fff;stroke-width:0.5;"})
    elem.setAttribute('d', svgPathFromPoints([[pos.e(1), -9999], [pos.e(1), 9999]]))   

  getOrCreateElem: (uri, groupId, tag, attrs) ->
    elem = @elemById[uri]
    if !elem
      elem = @elemById[uri] = document.createElementNS("http://www.w3.org/2000/svg", tag)
      @$[groupId].appendChild(elem)
      elem.setAttribute('id', uri)
      for k,v of attrs
        elem.setAttribute(k, v)
    return elem
    
  setNote: (uri, curvePts) ->
    elem = @getOrCreateElem(uri, 'notes', 'path', {style:"fill:#53774b; stroke:#000000; stroke-width:1.5;"})
    elem.setAttribute('d', svgPathFromPoints(curvePts))

  setCursor: (y1, h1, y2, h2, fullZoomX, zoomInX, cursor) ->
    @cursorPath =
      top: @querySelector('#cursor1')
      mid: @querySelector('#cursor2')
      bot: @querySelector('#cursor3')
    return if !@cursorPath.top
    
    xZoomedOut = fullZoomX(cursor.t())
    xZoomedIn = zoomInX(cursor.t())
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
