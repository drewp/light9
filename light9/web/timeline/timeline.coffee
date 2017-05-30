log = console.log
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'

ROW_COUNT = 7

# polymer dom-repeat is happy to shuffle children by swapping their
# attribute values, and it's hard to correctly setup/teardown your
# side effects if your attributes are changing before the detach
# call. This alternative to dom-repeat never reassigns
# attributes. But, it can't set up property bindings.
updateChildren = (parent, newUris, makeChild) ->
  childUris = []
  childByUri = {}
  for e in parent.children
    childUris.push(e.uri)
    childByUri[e.uri] = e

  for uri in _.difference(childUris, newUris)
    childByUri[uri].detached()
    childByUri[uri].remove()
  for uri in _.difference(newUris, childUris)
    parent.appendChild(makeChild(uri))


Polymer
  is: 'light9-timeline-editor'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    viewState: { type: Object }
    debug: {type: String}
    graph: {type: Object, notify: true}
    setAdjuster: {type: Function, notify: true}
    playerSong: {type: String, notify: true}
    followPlayerSong: {type: Boolean, notify: true, value: true}
    song: {type: String, notify: true}
    show: {value: 'http://light9.bigasterisk.com/show/dance2017'}
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
    d = 700 if d < 1 # bug is that asco isn't giving duration, but 0 makes the scale corrupt
    @viewState.zoomSpec.duration(d)
  setSong: (s) ->
    @song = @playerSong if @followPlayerSong

  ready: ->
    ko.options.deferUpdates = true;

    window.debug_zoomOrLayoutChangedCount = 0
    window.debug_adjUpdateDisplay = 0
    
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
    @setAdjuster = @$.adjustersCanvas.setAdjuster.bind(@$.adjustersCanvas)

    setInterval(@updateDebugSummary.bind(@), 100)

    #if anchor == loadtest
    #  add note and delete it repeatedly
    #  disconnect the graph, make many notes, drag a point over many steps, measure lag somewhere

  updateDebugSummary: ->
    elemCount = (tag) -> document.getElementsByTagName(tag).length
    @debug = "#{window.debug_zoomOrLayoutChangedCount} layout change,
     #{elemCount('light9-timeline-note')} notes,
     #{elemCount('light9-timeline-graph-row')} rows,
     #{window.debug_adjsCount} adjuster items registered,
     #{window.debug_adjUpdateDisplay} adjuster updateDisplay calls,
    "
    
  attached: ->
    @dia = @$.dia
    ko.computed(@zoomOrLayoutChanged.bind(@))
    ko.computed(@songTimeChanged.bind(@))

    @trackMouse()
    @bindKeys()
    @bindWheelZoom()
    @forwardMouseEventsToAdjustersCanvas()

    @makeZoomAdjs()

  zoomOrLayoutChanged: ->
    # not for cursor updates

    window.debug_zoomOrLayoutChangedCount++
    @fullZoomX.domain([0, @viewState.zoomSpec.duration()])
    @fullZoomX.range([0, @width()])

    # had trouble making notes update when this changes
    zoomInX = d3.scaleLinear()
    zoomInX.domain([@viewState.zoomSpec.t1(), @viewState.zoomSpec.t2()])
    zoomInX.range([0, @width()])
    @zoomInX = zoomInX

    # todo: these run a lot of work purely for a time change    
    @dia.setTimeAxis(@width(), @$.zoomed.$.audio.offsetTop, @zoomInX)
    @$.adjustersCanvas.updateAllCoords()

    # cursor needs update when layout changes, but I don't want
    # zoom/layout to depend on the playback time
    setTimeout(@songTimeChanged.bind(@), 1)

  songTimeChanged: ->
    @$.cursorCanvas.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
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

        @$.cursorCanvas.setMouse(@viewState.mouse.pos())
        # should be controlled by a checkbox next to follow-player-song-choice
        @sendMouseToVidref() unless window.location.hash.match(/novidref/)

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

  forwardMouseEventsToAdjustersCanvas: ->
    ac = @$.adjustersCanvas
    @addEventListener('mousedown', ac.onDown.bind(ac))
    @addEventListener('mousemove', ac.onMove.bind(ac))
    @addEventListener('mouseup', ac.onUp.bind(ac))

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
    shortcut.add "L", =>
      @$.adjustersCanvas.updateAllCoords()

  makeZoomAdjs: ->
    yMid = => @$.audio.offsetTop + @$.audio.offsetHeight / 2
    dur = @viewState.zoomSpec.duration
    
    valForPos = (pos) =>
        x = pos.e(1)
        t = @fullZoomX.invert(x)
    @setAdjuster('zoom-left', => new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t1,
      getTarget: () =>
        $V([@fullZoomX(@viewState.zoomSpec.t1()), yMid()])
      getSuggestedTargetOffset: () => $V([-50, 0])
      getValueForPos: valForPos
    }))

    @setAdjuster('zoom-right', => new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t2,
      getTarget: () =>
        $V([@fullZoomX(@viewState.zoomSpec.t2()), yMid()])
      getSuggestedTargetOffset: () => $V([50, 0])
      getValueForPos: valForPos
    }))

    panObs = ko.pureComputed({
        read: () =>
          (@viewState.zoomSpec.t1() + @viewState.zoomSpec.t2()) / 2
        write: (value) =>
          zs = @viewState.zoomSpec
          span = zs.t2() - zs.t1()
          zs.t1(value - span / 2)
          zs.t2(value + span / 2)
      })

    @setAdjuster('zoom-pan', => new AdjustableFloatObservable({
      observable: panObs
      emptyBox: true
      # fullzoom is not right- the sides shouldn't be able to go
      # offscreen
      getTarget: () => $V([@fullZoomX(panObs()), yMid()])
      getSuggestedTargetOffset: () => $V([0, 0])
      getValueForPos: valForPos
      }))
      

Polymer
  is: 'light9-timeline-time-zoomed'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    graph: { type: Object, notify: true }
    dia: { type: Object, notify: true }
    song: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
    rows: { value: [0...ROW_COUNT] }
    zoom: { type: Object, notify: true, observer: 'onZoom' }
    zoomFlattened: { type: Object, notify: true }
  onZoom: ->
    updateZoomFlattened = ->
      @zoomFlattened = ko.toJS(@zoom)
    ko.computed(updateZoomFlattened.bind(@))
  ready: ->

  attached: ->
    root = @closest('light9-timeline-editor')
    setupDrop(@, @$.rows, root, @onDrop.bind(@))

  onDrop: (effect, pos) ->
    U = (x) -> @graph.Uri(x)

    # we could probably accept some initial overrides right on the
    # effect uri, maybe as query params

    if not @graph.contains(effect, RDF + 'type', U(':Effect'))
      if @graph.contains(effect, RDF + 'type', U(':LightSample'))
        effect = @makeEffect(effect)
      else
        log("drop #{effect} is not an effect")
        return

    dropTime = @zoomInX.invert(pos.e(1))
    @makeNewNote(effect, dropTime)

  makeEffect: (uri) ->
    U = (x) -> @graph.Uri(x)
    effect = U(uri + '/effect')
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: effect}
    
    quads = [
      quad(effect, U('rdf:type'), U(':Effect')),
      quad(effect, U(':copiedFrom'), uri),
      quad(effect, U('rdfs:label'), @graph.Literal(uri.replace(/.*capture\//, ''))),
      quad(effect, U(':publishAttr'), U(':strength')),
      ]

    fromSettings = @graph.objects(uri, U(':setting'))

    toSettings = @graph.nextNumberedResources(effect + '_set', fromSettings.length)
      
    for fs in fromSettings
      ts = toSettings.pop()
      # full copies of these since I may have to delete captures
      quads.push(quad(effect, U(':setting'), ts))
      quads.push(quad(ts, U(':device'), @graph.uriValue(fs, U(':device'))))
      quads.push(quad(ts, U(':deviceAttr'), @graph.uriValue(fs, U(':deviceAttr'))))
      quads.push(quad(ts, U(':value'), @graph.uriValue(fs, U(':value'))))

    @graph.applyAndSendPatch({delQuads: [], addQuads: quads})
    return effect
        
  makeNewNote: (effect, dropTime) ->
    U = (x) -> @graph.Uri(x)
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: @song}
      
    newNote = @graph.nextNumberedResource("#{@song}/n")
    newCurve = @graph.nextNumberedResource("#{newNote}c")
    points = @graph.nextNumberedResources("#{newCurve}p", 4)

    curveQuads = [
        quad(@song, U(':note'), newNote)
        quad(newNote, RDF + 'type', U(':Note'))
        quad(newNote, U(':originTime'), @graph.LiteralRoundedFloat(dropTime))
        quad(newNote, U(':effectClass'), effect)
        quad(newNote, U(':curve'), newCurve)
        quad(newCurve, RDF + 'type', U(':Curve'))
        quad(newCurve, U(':attr'), U(':strength'))
      ]        
    pointQuads = []

    desiredWidthX = @offsetWidth * .3
    desiredWidthT = @zoomInX.invert(desiredWidthX) - @zoomInX.invert(0)
    
    for i in [0...4]
      pt = points[i]
      pointQuads.push(quad(newCurve, U(':point'), pt))
      pointQuads.push(quad(pt, U(':time'), @graph.LiteralRoundedFloat(i/3 * desiredWidthT)))
      pointQuads.push(quad(pt, U(':value'), @graph.LiteralRoundedFloat(i == 1 or i == 2)))

    patch = {
      delQuads: []
      addQuads: curveQuads.concat(pointQuads)
      }
    @graph.applyAndSendPatch(patch)

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
    'onGraph(graph, dia, setAdjuster, song, zoomInX)'
    'update(song, rowIndex)'
    'onZoom(zoomInX)'
    ]
  onGraph: ->
    @graph.runHandler(@update.bind(@), "row notes #{@rowIndex}")
  update: (patch) ->
    U = (x) -> @graph.Uri(x)

    notesForThisRow = []
    i = 0
    for n in _.sortBy(@graph.objects(@song, U(':note')))
      if (i % ROW_COUNT) == @rowIndex
        notesForThisRow.push(n)
      i++

    updateChildren @, notesForThisRow, (newUri) =>
      child = document.createElement('light9-timeline-note')
      child.graph = @graph
      child.dia = @dia
      child.uri = newUri
      child.setAdjuster = @setAdjuster
      child.song = @song # could change, but all the notes will be rebuilt
      child.zoomInX = @zoomInX # missing binding; see onZoom
      return child      

  onZoom: ->
    for e in @children
      e.zoomInX = @zoomInX


getCurvePoints = (graph, curve, xOffset) ->
  worldPts = []
  uris = graph.objects(curve, graph.Uri(':point'))
  for pt in uris
    v = $V([xOffset + graph.floatValue(pt, graph.Uri(':time')),
            graph.floatValue(pt, graph.Uri(':value'))])
    v.uri = pt
    worldPts.push(v)
  worldPts.sort((a,b) -> a.e(1) > b.e(1))
  return [uris, worldPts]

Polymer
  is: 'light9-timeline-note'
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'update'
  properties:
    graph: { type: Object, notify: true }
    dia: { type: Object, notify: true }
    uri: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
    setAdjuster: {type: Function, notify: true }
    inlineRect: { type: Object, notify: true }
  observers: [
    'onUri(graph, dia, uri, zoomInX, setAdjuster)'
    'update(graph, dia, uri, zoomInX, setAdjuster)'
    ]
  ready: ->
    @adjusterIds = {}

  detached: ->
    log('detatch', @uri)
    @dia.clearElem(@uri, ['/area', '/label'])
    @isDetached = true
    @clearAdjusters()

  clearAdjusters: ->
    for i in Object.keys(@adjusterIds)
      @setAdjuster(i, null)

  onUri: ->
    @graph.runHandler(@update.bind(@), "note updates #{@uri}")

  patchCouldAffectMe: (patch) ->
    if patch and patch.addQuads # sometimes patch is a polymer-sent value. @update is used as a listener too
      if patch.addQuads.length == patch.delQuads.length == 1
        add = patch.addQuads[0]
        del = patch.delQuads[0]
        if (add.predicate == del.predicate == @graph.Uri(':time') and
            add.subject == del.subject)
          timeEditFor = add.subject
          if @worldPts and timeEditFor not in @pointUris
            return false
    return true
      
            
  update: (patch) ->
    if not @patchCouldAffectMe(patch)
      # as autodep still fires all handlers on all patches, we just
      # need any single dep to cause another callback. (without this,
      # we would no longer be registered at all)
      @graph.subjects(@uri, @uri, @uri)
      return
    if @isDetached?
      return
 
    @updateDisplay()

  updateDisplay: ->
      
    # update our note DOM and SVG elements based on the graph
    U = (x) -> @graph.Uri(x)

    yForV = (v) => @offsetTop + (1 - v) * @offsetHeight

    originTime = @graph.floatValue(@uri, U(':originTime'))
    effect = @graph.uriValue(@uri, U(':effectClass'))
    for curve in @graph.objects(@uri, U(':curve'))
      if @graph.uriValue(curve, U(':attr')) == U(':strength')
        @updateStrengthCurveEtc(originTime, curve, yForV, effect)
        
  updateStrengthCurveEtc: (originTime, curve, yForV, effect) ->
    U = (x) -> @graph.Uri(x)
    [@pointUris, @worldPts] = getCurvePoints(@graph, curve, originTime) # (song time, value)

    curveWidth = =>
      tMin = @graph.floatValue(@worldPts[0].uri, U(':time'))
      tMax = @graph.floatValue(@worldPts[3].uri, U(':time'))
      tMax - tMin            

    screenPts = ($V([@zoomInX(pt.e(1)), @offsetTop + (1 - pt.e(2)) * @offsetHeight]) for pt in @worldPts)
    @dia.setNote(@uri, screenPts, effect)

    leftX = Math.max(2, screenPts[Math.min(1, screenPts.length - 1)].e(1) + 5)
    rightX = screenPts[Math.min(2, screenPts.length - 1)].e(1) - 5
    if screenPts.length < 3
      rightX = leftX + 120
    w = 150
    h = 80
    @inlineRect = {
      left: leftX,
      top: @offsetTop + @offsetHeight - h - 5,
      width: w,
      height: h,
      display: if rightX - leftX > w then 'block' else 'none'
      }

    if screenPts[screenPts.length - 1].e(1) - screenPts[0].e(1) < 100
      @clearAdjusters()
      # also kill their connectors
      return

    @makeCurveAdjusters(curveWidth, yForV, @worldPts)
    
  makeCurveAdjusters: (curveWidth, yForV, worldPts) ->
    U = (x) -> @graph.Uri(x)

    if true
      @adjusterIds[@uri+'/offset'] = true
      @setAdjuster(@uri+'/offset', => new AdjustableFloatObject({
        graph: @graph
        subj: @uri
        pred: U(':originTime')
        ctx: U(@song)
        getDisplayValue: (v, dv) => "o=#{dv}"
        getTargetPosForValue: (value) =>
          # display bug: should be working from pt[0].t, not from origin
          $V([@zoomInX(value + curveWidth() / 2), yForV(.5)])
        getValueForPos: (pos) =>
          @zoomInX.invert(pos.e(1)) - curveWidth() / 2
        getSuggestedTargetOffset: () => $V([-10, 0])
      }))

    for pointNum in [0, 1, 2, 3]
      do (pointNum) =>
        @adjusterIds[@uri+'/p'+pointNum] = true
        @setAdjuster(@uri+'/p'+pointNum, =>
            adj = new AdjustableFloatObject({
              graph: @graph
              subj: worldPts[pointNum].uri
              pred: U(':time')
              ctx: U(@song)
              getTargetPosForValue: (value) =>
                $V([@zoomInX(value),
                    yForV(worldPts[pointNum].e(2))])
              getValueForPos: (pos) =>
                origin = @graph.floatValue(@uri, U(':originTime'))
                (@zoomInX.invert(pos.e(1)) - origin)
              getSuggestedTargetOffset: () => $V([0, (if worldPts[pointNum].e(2) > .5 then 30 else -30)])
            })
            adj._getValue = (=>
              # note: don't use originTime from the closure- we need the
              # graph dependency
              adj._currentValue + @graph.floatValue(@uri, U(':originTime'))
              )
            adj
          )

    
    

Polymer
  is: "light9-timeline-note-inline-attrs"
  properties:
    graph: { type: Object, notify: true }
    song: { type: String, notify: true }
    uri: { type: String, notify: true }  # the Note
    rect: { type: Object, notify: true }
    effect: { type: String, notify: true }
    effectLabel: { type: String, notify: true }
    colorScale: { type: String, notify: true }
    noteLabel: { type: String, notify: true }
  observers: [
    'addHandler(graph, uri)'
    'onColorScale(graph, uri, colorScale)'
    ]
  onColorScale: ->
    U = (x) -> @graph.Uri(x)
    if @colorScale == @colorScaleFromGraph
      return
      
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: @song}

    settingValue = @graph.Literal(@colorScale)
    if @existingColorScaleSetting
      @graph.patchObject(@existingColorScaleSetting, U(':value'), settingValue, @song)
    else
      setting = @graph.nextNumberedResource(@uri + 'set')
      patch = {delQuads: [], addQuads: [
        quad(@uri, U(':setting'), setting)
        quad(setting, U(':effectAttr'), U(':colorScale'))
        quad(setting, U(':value'), settingValue)
        ]}
      @graph.applyAndSendPatch(patch)
    
  addHandler: ->
    @graph.runHandler(@update.bind(@))
    
  update: ->
    console.time('attrs update')
    U = (x) -> @graph.Uri(x)
    @effect = @graph.uriValue(@uri, U(':effectClass'))
    @effectLabel = @graph.stringValue(@effect, U('rdfs:label')) or (@effect.replace(/.*\//, ''))
    @noteLabel = @uri.replace(/.*\//, '')

    @existingColorScaleSetting = null
    for setting in @graph.objects(@uri, U(':setting'))
      ea = @graph.uriValue(setting, U(':effectAttr'))
      value = @graph.stringValue(setting, U(':value'))
      if ea == U(':colorScale')
        @colorScaleFromGraph = value
        @colorScale = value
        @existingColorScaleSetting = setting
    if @existingColorScaleSetting == null
      @colorScaleFromGraph = '#ffffff'
      @colorScale = '#ffffff'
    console.timeEnd('attrs update')


  onDel: ->
    patch = {delQuads: [{subject: @song, predicate: @graph.Uri(':note'), object: @uri, graph: @song}], addQuads: []}
    @graph.applyAndSendPatch(patch)

    
class deleteme
  go: ->
    visible: { type: Boolean, notify: true }
    
    displayValue: { type: String }
    centerStyle: { type: Object }
    spanClass: { type: String, value: '' }

  observer: [
    'onAdj(graph, adj, dia, id, visible)'
    ]
  onAdj:  ->
    log('onAdj', @id)
    @adj.subscribe(@updateDisplay.bind(this))
    @graph.runHandler(@updateDisplay.bind(@))

  updateDisplay: () ->
    go = =>
      if !@visible
        @clearElements()
        return
      window.debug_adjUpdateDisplay++
      @spanClass = if @adj.config.emptyBox then 'empty' else ''
      @displayValue = @adj.getDisplayValue()
      center = @adj.getCenter()
      target = @adj.getTarget()
      #log("adj updateDisplay center #{center.elements} target #{target.elements}")
      return if isNaN(center.e(1))
      @centerStyle = {x: center.e(1), y: center.e(2)}
      @dia.setAdjusterConnector(@adj.id + '/conn', center, target)
    @debounce('updateDisplay', go)
        
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

    @updateDisplay()

  detached: -> @clearElements()
  clearElements: ->
    @dia.clearElem(@adj.id, ['/conn'])


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

_line = (ctx, p1, p2) ->
  ctx.moveTo(p1.e(1), p1.e(2))
  ctx.lineTo(p2.e(1), p2.e(2))

# http://stackoverflow.com/a/4959890
_roundRect = (ctx, sx,sy,ex,ey,r) ->
    d2r = Math.PI/180
    r = ( ( ex - sx ) / 2 ) if ( ex - sx ) - ( 2 * r ) < 0 # ensure that the radius isn't too large for x
    r = ( ( ey - sy ) / 2 ) if ( ey - sy ) - ( 2 * r ) < 0 # ensure that the radius isn't too large for y
    ctx.beginPath();
    ctx.moveTo(sx+r,sy);
    ctx.lineTo(ex-r,sy);
    ctx.arc(ex-r,sy+r,r,d2r*270,d2r*360,false);
    ctx.lineTo(ex,ey-r);
    ctx.arc(ex-r,ey-r,r,d2r*0,d2r*90,false);
    ctx.lineTo(sx+r,ey);
    ctx.arc(sx+r,ey-r,r,d2r*90,d2r*180,false);
    ctx.lineTo(sx,sy+r);
    ctx.arc(sx+r,sy+r,r,d2r*180,d2r*270,false);
    ctx.closePath();


Polymer
  is: 'light9-cursor-canvas'
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'update'

  ready: ->
    @mouseX = 0
    @mouseY = 0
    @cursorPath = null
    @ctx = @$.canvas.getContext('2d')

  update: (ev) ->
    @$.canvas.width = ev.target.offsetWidth
    @$.canvas.height = ev.target.offsetHeight
    @redraw()

  setMouse: (pos) ->
    @mouseX = pos.e(1)
    @mouseY = pos.e(2)
    @redraw()

  setCursor: (y1, h1, y2, h2, fullZoomX, zoomInX, cursor) ->
    
    xZoomedOut = fullZoomX(cursor.t())
    xZoomedIn = zoomInX(cursor.t())

    @cursorPath = {
      top0: $V([xZoomedOut, y1])
      top1: $V([xZoomedOut, y1 + h1])
      mid0: $V([xZoomedIn + 2, y2 + h2])
      mid1: $V([xZoomedIn - 2, y2 + h2])
      mid2: $V([xZoomedOut - 1, y1 + h1])
      mid3: $V([xZoomedOut + 1, y1 + h1])
      bot0: $V([xZoomedIn, y2 + h2])
      bot1: $V([xZoomedIn, @offsetParent.offsetHeight])
    }
    @redraw()

  redraw: ->
    @ctx.clearRect(0, 0, @$.canvas.width, @$.canvas.height)

    @ctx.strokeStyle = '#fff'
    @ctx.lineWidth = 0.5
    @ctx.beginPath()
    _line(@ctx, $V([0, @mouseY]), $V([@$.canvas.width, @mouseY]))
    _line(@ctx, $V([@mouseX, 0]), $V([@mouseX, @$.canvas.height]))
    @ctx.stroke()

    if @cursorPath
      @ctx.strokeStyle = '#ff0303'
      @ctx.lineWidth = 1.5
      @ctx.beginPath()
      _line(@ctx, @cursorPath.top0, @cursorPath.top1)
      @ctx.stroke()

      @ctx.fillStyle = '#9c0303'
      @ctx.beginPath()
      @ctx.moveTo(@cursorPath.mid0.e(1), @cursorPath.mid0.e(2))
      @ctx.lineTo(p.e(1), p.e(2)) for p in [
        @cursorPath.mid1, @cursorPath.mid2, @cursorPath.mid3]
      @ctx.fill()
      
      @ctx.strokeStyle = '#ff0303'
      @ctx.lineWidth = 3
      @ctx.beginPath()
      _line(@ctx, @cursorPath.bot0, @cursorPath.bot1, '#ff0303', '3px')
      @ctx.stroke()
    
Polymer
  is: 'light9-adjusters-canvas'
  behaviors: [ Polymer.IronResizableBehavior ]
  properties:
    adjs: { type: Object, notify: true }, # adjId: Adjustable
  observers: [
    'updateAllCoords(adjs)'
  ]
  listeners:
    'iron-resize': 'resizeUpdate'
  ready: ->
    @adjs = {}
    @ctx = @$.canvas.getContext('2d')

    @redraw()
   
  onDown: (ev) ->
    if ev.buttons == 1
      ev.stopPropagation()
      start = $V([ev.x, ev.y])
      adj = @_adjAtPoint(start)
      if adj
        @currentDrag = {start: start, adj: adj}
        adj.startDrag()

  onMove: (ev) ->
    pos = $V([ev.x, ev.y])
    if @currentDrag
      @currentDrag.cur = pos
      @currentDrag.adj.continueDrag(@currentDrag.cur.subtract(@currentDrag.start))

  onUp: (ev) ->
    return unless @currentDrag
    @currentDrag.adj.endDrag()
    @currentDrag = null
    
  setAdjuster: (adjId, makeAdjustable) ->
    # callers register/unregister the Adjustables they want us to make
    # adjuster elements for. Caller invents adjId.  makeAdjustable is
    # a function returning the Adjustable or it is null to clear any
    # adjusters with this id.
    if not @adjs[adjId] or not makeAdjustable?
      if not makeAdjustable?
        delete @adjs[adjId]
      else
        adj = makeAdjustable()
        @adjs[adjId] = adj
        adj.id = adjId

    @redraw()

    window.debug_adjsCount = Object.keys(@adjs).length

  updateAllCoords: ->
    @redraw()

  _adjAtPoint: (pt) ->
    nearest = @qt.find(pt.e(1), pt.e(2))
    if not nearest? or nearest.distanceFrom(pt) > 50
      return null
    return nearest?.adj

  resizeUpdate: (ev) ->
    @$.canvas.width = ev.target.offsetWidth
    @$.canvas.height = ev.target.offsetHeight
    @redraw()

  redraw: (adjs) ->
    @debounce('redraw', @_throttledRedraw.bind(@))

  _throttledRedraw: () ->
    console.time('adjs redraw')
    @_layoutCenters()
    
    @ctx.clearRect(0, 0, @$.canvas.width, @$.canvas.height)

    for adjId, adj of @adjs
      ctr = adj.getCenter()
      target = adj.getTarget()
      @_drawConnector(ctr, target)
      
      @_drawAdjuster(adj.getDisplayValue(),
                     Math.floor(ctr.e(1)) - 20, Math.floor(ctr.e(2)) - 10,
                     Math.floor(ctr.e(1)) + 20, Math.floor(ctr.e(2)) + 10)
    console.timeEnd('adjs redraw')

  _layoutCenters: ->
    # push Adjustable centers around to avoid overlaps
    # Todo: also don't overlap inlineattr boxes
    # Todo: don't let their connector lines cross each other
    @qt = d3.quadtree([], ((d)->d.e(1)), ((d)->d.e(2)))
    @qt.extent([[0,0], [8000,8000]])
    for _, adj of @adjs
      desired = adj.getSuggestedCenter()
      output = desired
      for tries in [0...2]
        nearest = @qt.find(output.e(1), output.e(2))
        if nearest
          dist = output.distanceFrom(nearest)
          if dist < 60
            away = output.subtract(nearest).toUnitVector()
            toScreenCenter = $V([500,200]).subtract(output).toUnitVector()
            output = output.add(away.x(60).add(toScreenCenter.x(10)))

      if -50 < output.e(1) < 20 # mostly for zoom-left
        output.setElements([
          Math.max(20, output.e(1)),
          output.e(2)])
        
      adj.centerOffset = output.subtract(adj.getTarget())
      output.adj = adj
      @qt.add(output)

  _drawConnector: (ctr, target) ->
    @ctx.strokeStyle = '#aaa'
    @ctx.lineWidth = 2
    @ctx.beginPath()
    _line(@ctx, ctr, target)
    @ctx.stroke()
    
  _drawAdjuster: (label, x1, y1, x2, y2) ->
    radius = 8

    @ctx.shadowColor = 'black'
    @ctx.shadowBlur = 15
    @ctx.shadowOffsetX = 5
    @ctx.shadowOffsetY = 9
    
    @ctx.fillStyle = 'rgba(255, 255, 0, 0.5)'
    @ctx.beginPath()
    _roundRect(@ctx, x1, y1, x2, y2, radius)
    @ctx.fill()

    @ctx.shadowColor = 'rgba(0,0,0,0)'
        
    @ctx.strokeStyle = 'yellow'
    @ctx.lineWidth = 2
    @ctx.setLineDash([3, 3])
    @ctx.beginPath()
    _roundRect(@ctx, x1, y1, x2, y2, radius)
    @ctx.stroke()
    @ctx.setLineDash([])

    @ctx.font = "12px sans"
    @ctx.fillStyle = '#000'
    @ctx.fillText(label, x1 + 5, y2 - 5, x2 - x1 - 10)

    # coords from a center that's passed in
    # # special layout for the thaeter ones with middinh 
    # l/r arrows
    # connector

  
Polymer
  # note boxes
  is: 'light9-timeline-diagram-layer'
  properties: {}
  ready: ->
    @elemById = {}

  setTimeAxis: (width, yTop, scale) ->
    pxPerTick = 50
    axis = d3.axisTop(scale).ticks(width / pxPerTick)
    d3.select(@$.timeAxis).attr('transform', 'translate(0,'+yTop+')').call(axis)

  getOrCreateElem: (uri, groupId, tag, attrs) ->
    elem = @elemById[uri]
    if !elem
      elem = @elemById[uri] = document.createElementNS("http://www.w3.org/2000/svg", tag)
      @$[groupId].appendChild(elem)
      elem.setAttribute('id', uri)
      for k,v of attrs
        elem.setAttribute(k, v)
    return elem

  clearElem: (uri, suffixes) -> # todo: caller shouldn't have to know suffixes!
    for suff in suffixes
      elem = @elemById[uri+suff]
      if elem
        elem.remove()
        delete @elemById[uri+suff]

  anyPointsInView: (pts) ->
    for pt in pts
      # wrong:
      if pt.e(1) > -100 && pt.e(1) < 2500
        return true
    return false
    
  setNote: (uri, curvePts, effect) ->
    areaId = uri + '/area'
    labelId = uri + '/label'
    if not @anyPointsInView(curvePts)
      @clearElem(uri, ['/area', '/label'])
      return
    # for now these need to be pretty transparent since they're
    # drawing on top of the inline-attrs widget :(

    if effect in ['http://light9.bigasterisk.com/effect/blacklight',
      'http://light9.bigasterisk.com/effect/strobewarm']
      hue = 0
      sat = 100
    else        
      hash = 0
      for i in [(effect.length-10)...effect.length]
        hash += effect.charCodeAt(i)
      hue = (hash * 8) % 360
      sat = 40 + (hash % 20) # don't conceal colorscale too much
    
    elem = @getOrCreateElem(areaId, 'notes', 'path',
      {style:"fill:hsla(#{hue}, #{sat}%, 58%, 0.313); stroke:#000000; stroke-width:1.5;"})
    elem.setAttribute('d', svgPathFromPoints(curvePts))

    #elem = @getOrCreateElem(uri+'/label', 'noteLabels', 'text', {style: "font-size:13px;line-height:125%;font-family:'Verana Sans';text-align:start;text-anchor:start;fill:#000000;"})
    #elem.setAttribute('x', curvePts[0].e(1)+20)
    #elem.setAttribute('y', curvePts[0].e(2)-10)
    #elem.innerHTML = effectLabel;

  setAdjusterConnector: (uri, center, target) ->
    id = uri + '/adj'
    if not @anyPointsInView([center, target])
      @clearElem(id, [''])
      return
    elem = @getOrCreateElem(uri, 'connectors', 'path', {style: "fill:none;stroke:#d4d4d4;stroke-width:0.9282527;stroke-linecap:butt;stroke-linejoin:miter;stroke-miterlimit:4;stroke-dasharray:2.78475821, 2.78475821;stroke-dashoffset:0;"})
    elem.setAttribute('d', svgPathFromPoints([center, target]))
