log = console.log
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'

Polymer
  is: 'light9-timeline-editor'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    viewState: { type: Object }
    debug: {type: String}
    graph: {type: Object, notify: true}
    playerSong: {type: String, notify: true}
    followPlayerSong: {type: Boolean, notify: true, value: true}
    song: {type: String, notify: true}
    show: {value: 'http://light9.bigasterisk.com/show/dance2016'}
    songTime: {type: Number, notify: true, observer: '_onSongTime'}
    songDuration: {type: Number, notify: true, observer: '_onSongDuration'}
    songPlaying: {type: Boolean, notify: true}
    fullZoomX: {type: Object, notify: true}
    zoomInX: {type: Object, notify: true}
  width: ko.observable(1)
  listeners:
    'iron-resize': '_onIronResize'
  observers: [
    'setSong(playerSong, followPlayerSong)'
    ]
  _onIronResize: ->
    @width(@offsetWidth)
  _onSongTime: (t) ->
    @viewState.cursor.t(t)
  _onSongDuration: (d) ->
    @viewState.zoomSpec.duration(d)
  setSong: (s) ->
    @song = @playerSong if @followPlayerSong

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
    @fullZoomX = d3.scaleLinear()
    @zoomInX = d3.scaleLinear()
  attached: ->
    @dia = @$.dia
    ko.computed(@zoomOrLayoutChanged.bind(@)).extend({rateLimit: 5})
    ko.computed(@songTimeChanged.bind(@))

    @adjs = @makeZoomAdjs()

    @trackMouse()
    @bindKeys()
    @bindWheelZoom()

  zoomOrLayoutChanged: ->
    @fullZoomX.domain([0, @viewState.zoomSpec.duration()])
    @fullZoomX.range([0, @width()])

    # had trouble making notes update when this changes
    zoomInX = d3.scaleLinear()
    zoomInX.domain([@viewState.zoomSpec.t1(), @viewState.zoomSpec.t2()])
    zoomInX.range([0, @width()])
    @zoomInX = zoomInX

    # todo: these run a lot of work purely for a time change    
    @dia.setTimeAxis(@width(), @$.zoomed.$.audio.offsetTop, @zoomInX)
    @$.adjusters.updateAllCoords()

    @songTimeChanged()

  songTimeChanged: ->
    @dia.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                     @$.zoomed.$.time.offsetTop,
                     @$.zoomed.$.time.offsetHeight,
                     @fullZoomX, @zoomInX, @viewState.cursor)
    
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

        @dia.setMouse(@viewState.mouse.pos())
        #@sendMouseToVidref()

  sendMouseToVidref: ->
    now = Date.now()
    if (!@$.vidrefLastSent? || @$.vidrefLastSent < now - 200) && !@songPlaying
      @$.vidrefTime.body = {t: @latestMouseTime(), source: 'timeline'}
      @$.vidrefTime.generateRequest()
      @$.vidrefLastSent = now

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
  is: 'light9-timeline-time-zoomed'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    graph: { type: Object, notify: true }
    dia: { type: Object, notify: true }
    song: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
    rows: { value: [0, 1, 2] }
    zoom: { type: Object, notify: true, observer: 'onZoom' }
    zoomFlattened: { type: Object, notify: true }
  onZoom: ->
    updateZoomFlattened = ->
      @zoomFlattened = ko.toJS(@zoom)
    ko.computed(updateZoomFlattened.bind(@))
  ready: ->

  attached: ->
    root = @closest('light9-timeline-editor')
    setupDrop @, @$.rows, root, (effect, pos) =>

      if not @graph.contains(effect, RDF + 'type', @graph.Uri(':Effect'))
        log("drop #{effect} is not an effect")
        return
      
      dropTime = @zoomInX.invert(pos.e(1))
      
      U = (x) -> @graph.Uri(x)

      nextNumberedResources = (graph, base, howMany) ->
        results = []
        # we could cache [base,lastSerial]
        for serial in [0..1000]
          uri = graph.Uri("#{base}#{serial}")
          if not graph.contains(uri, null, null)
            results.push(uri)
            if results.length >= howMany
              return results
        throw new Error("can't make sequential uri with base #{base}")

      nextNumberedResource = (graph, base) ->
        nextNumberedResources(graph, base, 1)[0]       
      
      newNote = nextNumberedResource(graph, "#{@song}/n")
      newCurve = nextNumberedResource(graph, "#{newNote}c")
      points = nextNumberedResources(graph, "#{newCurve}p", 4)
      
      quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: @song}

      curveQuads = [
          quad(@song, U(':note'), newNote)
          quad(newNote, RDF + 'type', U(':Note'))
          quad(newNote, U(':originTime'), @graph.LiteralRoundedFloat(dropTime))
          quad(newNote, U(':curve'), newCurve)
          quad(newCurve, RDF + 'type', U(':Curve'))
          quad(newCurve, U(':attr'), U(':strength'))
        ]        
      pointQuads = []
      for i in [0...4]
        pt = points[i]
        pointQuads.push(quad(newCurve, U(':point'), pt))
        pointQuads.push(quad(pt, U(':time'), @graph.LiteralRoundedFloat(i)))
        pointQuads.push(quad(pt, U(':value'), @graph.LiteralRoundedFloat(i == 1 or i == 2)))
      
      patch = {
        delQuads: []
        addQuads: curveQuads.concat(pointQuads)
        }
      @graph.applyAndSendPatch(patch)
      log('land', effect, dropTime, newNote)
      

Polymer
  is: "light9-timeline-time-axis",
  # for now since it's just one line calling dia,
  # light9-timeline-editor does our drawing work.

Polymer
  is: 'light9-timeline-graph-row'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    graph: { type: Object, notify: true }
    dia: { type: Object, notify: true }
    song:  { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
    noteUris: { type: Array, notify: true }
    rowIndex: { type: Object, notify: true }
  observers: [
    'onGraph(graph)'
    'update(song)'
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
    dia: { type: Object, notify: true }
    uri: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
  observers: [
    'onUri(graph, dia, uri)'
    'update(graph, dia, uri, zoomInX)'
    ]
  ready: ->

  detached: ->
    @dia.clearElem(@uri)

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

      @dia.setNote(@uri, (screenPos(pt) for pt in worldPts))

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
    window.adjDragUpdates++ if window.adjDragUpdates?
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

    @updateDisplay()

  detached: ->
    @dia.clearElem(@myId)


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

  clearElem: (uri) ->
    elem = @elemById[uri]
    if elem
      elem.remove()
      delete @elemById[uri]
    
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
