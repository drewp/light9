log = console.log
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
Drawing = window.Drawing
ROW_COUNT = 7

class Project
  constructor: (@graph) ->

  makeEffect: (uri) ->
    U = (x) => @graph.Uri(x)
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
      try
        quads.push(quad(ts, U(':value'), @graph.uriValue(fs, U(':value'))))
      catch
        quads.push(quad(ts, U(':scaledValue'), @graph.uriValue(fs, U(':scaledValue'))))

    @graph.applyAndSendPatch({delQuads: [], addQuads: quads})
    return effect

  makeNewNote: (effect, dropTime, desiredWidthT) ->
    U = (x) => @graph.Uri(x)
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
    
  getCurvePoints: (curve, xOffset) ->
    worldPts = []
    uris = @graph.objects(curve, @graph.Uri(':point'))
    for pt in uris
      tm = @graph.floatValue(pt, @graph.Uri(':time'))
      val = @graph.floatValue(pt, @graph.Uri(':value'))
      v = $V([xOffset + tm, val])
      v.uri = pt
      worldPts.push(v)
    worldPts.sort((a,b) -> a.e(1) > b.e(1))
    return [uris, worldPts]

  curveWidth: (worldPts) ->
    tMin = @graph.floatValue(worldPts[0].uri, @graph.Uri(':time'))
    tMax = @graph.floatValue(worldPts[3].uri, @graph.Uri(':time'))
    tMax - tMin
      
  deleteNote: (song, note, selection) ->
    patch = {delQuads: [{subject: song, predicate: graph.Uri(':note'), object: note, graph: song}], addQuads: []}
    @graph.applyAndSendPatch(patch)
    if note in selection.selected()
      selection.selected(_.without(selection.selected(), note))

class ViewState
  constructor: () ->
    # caller updates all these observables
    @width = ko.observable(500)
    @zoomSpec =
      duration: ko.observable(100) # current song duration
      t1: ko.observable(0)
      t2: ko.observable(100)
    @cursor =
      t: ko.observable(20)
    @mouse =
      pos: ko.observable($V([0,0]))
      
    @fullZoomX = d3.scaleLinear()
    @zoomInX = d3.scaleLinear()

    ko.computed(@zoomOrLayoutChanged.bind(@))    
    
  zoomOrLayoutChanged: () ->
    log('zoomOrLayoutChanged')
    # not for cursor updates

    window.debug_zoomOrLayoutChangedCount++

    if @zoomSpec.t1() < 0
      @zoomSpec.t1(0)
    if @zoomSpec.duration() and @zoomSpec.t2() > @zoomSpec.duration()
      @zoomSpec.t2(@zoomSpec.duration())

    @fullZoomX.domain([0, @zoomSpec.duration()])
    @fullZoomX.range([0, @width()])

    # had trouble making notes update when this changes
    zoomInX = d3.scaleLinear()
    zoomInX.domain([@zoomSpec.t1(), @zoomSpec.t2()])
    zoomInX.range([0, @width()])
    @zoomInX = zoomInX
    
  latestMouseTime: ->
    @zoomInX.invert(@mouse.pos().e(1))

  onMouseWheel: (deltaY) ->
    zs = @zoomSpec

    center = @latestMouseTime()
    left = center - zs.t1()
    right = zs.t2() - center
    scale = Math.pow(1.005, deltaY)

    zs.t1(center - left * scale)
    zs.t2(center + right * scale)
    log('view to', ko.toJSON(@))

    
class TimelineEditor extends Polymer.Element
  @is: 'light9-timeline-editor'
  @behaviors: [ Polymer.IronResizableBehavior ]
  @properties:
    viewState: { type: Object }
    debug: {type: String}
    graph: {type: Object, notify: true}
    project: {type: Object}
    setAdjuster: {type: Function, notify: true}
    playerSong: {type: String, notify: true}
    followPlayerSong: {type: Boolean, notify: true, value: true}
    song: {type: String, notify: true}
    show: {value: 'http://light9.bigasterisk.com/show/dance2017'}
    songTime: {type: Number, notify: true, observer: '_onSongTime'}
    songDuration: {type: Number, notify: true, observer: '_onSongDuration'}
    songPlaying: {type: Boolean, notify: true}
    selection: {type: Object, notify: true}
  width: ko.observable(1)
  @listeners:
    'iron-resize': '_onIronResize'
  @observers: [
    'setSong(playerSong, followPlayerSong)',
    'onGraph(graph)',
    ]
    
  connectedCallback: ->
    super.connectedCallback()
    ko.options.deferUpdates = true;

    @dia = @$.dia

    @selection = {hover: ko.observable(null), selected: ko.observable([])}

    window.debug_zoomOrLayoutChangedCount = 0
    window.debug_adjUpdateDisplay = 0
    
    @viewState = new ViewState()
    window.viewState = @viewState
    @setAdjuster = (adjId, makeAdjustable) =>
      ac = @$.adjustersCanvas
      setTimeout((()=>ac.setAdjuster(adjId, makeAdjustable)),10)

    setTimeout =>
      ko.computed(@zoomOrLayoutChanged.bind(@))
      ko.computed(@songTimeChanged.bind(@))

      @trackMouse()
      @bindKeys()
      @bindWheelZoom(@dia)
      setTimeout => # depends on child node being ready
          @forwardMouseEventsToAdjustersCanvas()
        , 400

      @makeZoomAdjs()

      zoomed = @$.zoomed
      setupDrop(@$.dia.shadowRoot.querySelector('svg'),
                zoomed.$.rows, @, zoomed.onDrop.bind(zoomed))

      setInterval(@updateDebugSummary.bind(@), 100)
    , 500

    #if anchor == loadtest
    #  add note and delete it repeatedly
    #  disconnect the graph, make many notes, drag a point over many steps, measure lag somewhere

  _onIronResize: ->
    @width(@offsetWidth)
  _onSongTime: (t) ->
    #@viewState.cursor.t(t)
  _onSongDuration: (d) ->
    d = 700 if d < 1 # bug is that asco isn't giving duration, but 0 makes the scale corrupt
    #@viewState.zoomSpec.duration(d)
    
  setSong: (s) ->
    @song = @playerSong if @followPlayerSong
  onGraph: (graph) ->
    @project = new Project(graph)

  updateDebugSummary: ->
    elemCount = (tag) -> document.getElementsByTagName(tag).length
    @debug = "#{window.debug_zoomOrLayoutChangedCount} layout change,
     #{elemCount('light9-timeline-note')} notes,
     #{@selection.selected().length} selected
     #{elemCount('light9-timeline-graph-row')} rows,
     #{window.debug_adjsCount} adjuster items registered,
     #{window.debug_adjUpdateDisplay} adjuster updateDisplay calls,
    "

  zoomOrLayoutChanged: ->
  
    vs = @viewState
    
  
    # todo: these run a lot of work purely for a time change
    if @$.zoomed?.$?.audio?
      @dia.setTimeAxis(@width(), @$.zoomed.$.audio.offsetTop, vs.zoomInX)
      @$.adjustersCanvas.updateAllCoords()

    # cursor needs update when layout changes, but I don't want
    # zoom/layout to depend on the playback time
    setTimeout(@songTimeChanged.bind(@), 1)

  songTimeChanged: ->
    return unless @$.zoomed?.$?.time?
    @$.cursorCanvas.setCursor(@$.audio.offsetTop, @$.audio.offsetHeight,
                              @$.zoomed.$.time.offsetTop,
                              @$.zoomed.$.time.offsetHeight,
                              @viewState)
    
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

  

  bindWheelZoom: (elem) ->
    elem.addEventListener 'mousewheel', (ev) =>
      @viewState.onMouseWheel(ev.deltaY)

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
    shortcut.add 'Delete', =>
      for note in @selection.selected()
        @project.deleteNote(@song, note, @selection)

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
      getSuggestedTargetOffset: () => $V([50, 0])
      getValueForPos: valForPos
    }))

    @setAdjuster('zoom-right', => new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t2,
      getTarget: () =>
        $V([@fullZoomX(@viewState.zoomSpec.t2()), yMid()])
      getSuggestedTargetOffset: () => $V([-50, 0])
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
      
customElements.define(TimelineEditor.is, TimelineEditor)

# plan: in here, turn all the notes into simple js objects with all
# their timing data and whatever's needed for adjusters. From that, do
# the brick layout. update only changing adjusters.
class TimeZoomed extends Polymer.Element
  @is: 'light9-timeline-time-zoomed'
  @behaviors: [ Polymer.IronResizableBehavior ]
  @properties:
    graph: { type: Object, notify: true }
    project: { type: Object }
    selection: { type: Object, notify: true }
    dia: { type: Object, notify: true }
    song: { type: String, notify: true }
    viewState: { type: Object, notify: true }
  @observers: [
    'onGraph(graph, setAdjuster, song, viewState, project)',
    'onZoom(viewState)',
  ]
  @listeners: {'iron-resize': 'update'}
  update: ->
    @renderer.resize(@clientWidth, @clientHeight)
    @renderer.render(@stage)

  onZoom: ->
    updateZoomFlattened = ->
      log('updateZoomFlattened')
      @zoomFlattened = ko.toJS(@viewState.zoomSpec)
    ko.computed(updateZoomFlattened.bind(@))

  constructor: ->
    super()
    @stage = new PIXI.Container()
    
    @renderer = PIXI.autoDetectRenderer({
         backgroundColor: 0xff6060,
    })
     
  connectedCallback: ->
    super.connectedCallback()
     
    @$.rows.appendChild(@renderer.view);
  
    # iron-resize should be doing this but it never fires
    setInterval(@update.bind(@), 1000)
    
  onGraph: ->
    @graph.runHandler(@gatherNotes.bind(@), 'zoom notes')
  gatherNotes: ->
    U = (x) => @graph.Uri(x)

    log('assign rows',@song, 'graph has', @graph.quads().length)
    graphics = new PIXI.Graphics({nativeLines: true})

    for uri in _.sortBy(@graph.objects(@song, U(':note')), 'uri')
      #should only make new ones
      # 
      child = new Note(@graph, @selection, @dia, uri, @setAdjuster, @song, @viewState.zoomInX)
      originTime = @graph.floatValue(uri, U(':originTime'))
      effect = @graph.uriValue(uri, U(':effectClass'))
      for curve in @graph.objects(uri, U(':curve'))
        if @graph.uriValue(curve, U(':attr')).equals(U(':strength'))

          [@pointUris, @worldPts] = @project.getCurvePoints(curve, originTime)
          curveWidthCalc = () => @_curveWidth(@worldPts)

          h = 150 #@offsetHeight
          screenPts = ($V([@viewState.zoomInX(pt.e(1)), @offsetTop + (1 - pt.e(2)) * h]) for pt in @worldPts)
          graphics.beginFill(0xFF3300);
          graphics.lineStyle(4, 0xffd900, 1)

          graphics.moveTo(screenPts[0].e(1), screenPts[0].e(2))
          for p in screenPts.slice(1)
            graphics.lineTo(p.e(1), p.e(2))
         graphics.endFill()
    
     @rows = []#(new NoteRow(@graph, @dia, @song, @zoomInX, @noteUris, i, @selection) for i in [0...ROW_COUNT])

     @stage.children.splice(0)
     @stage.addChild(graphics)
     @renderer.render(@stage)
    
  onDrop: (effect, pos) ->
    U = (x) => @graph.Uri(x)

    return unless effect and effect.match(/^http/)

    # we could probably accept some initial overrides right on the
    # effect uri, maybe as query params

    if not @graph.contains(effect, RDF + 'type', U(':Effect'))
      if @graph.contains(effect, RDF + 'type', U(':LightSample'))
        effect = @project.makeEffect(effect)
      else
        log("drop #{effect} is not an effect")
        return

    dropTime = @viewState.zoomInX.invert(pos.e(1))

    desiredWidthX = @offsetWidth * .3
    desiredWidthT = @viewState.zoomInX.invert(desiredWidthX) - @viewState.zoomInX.invert(0)
    desiredWidthT = Math.min(desiredWidthT, @zoom.duration() - dropTime)
    @project.makeNewNote(effect, dropTime, desiredWidthT)
        
customElements.define(TimeZoomed.is, TimeZoomed)

class TimeAxis extends Polymer.Element
  @is: "light9-timeline-time-axis",
  # for now since it's just one line calling dia,
  # light9-timeline-editor does our drawing work.

customElements.define(TimeAxis.is, TimeAxis)

class NoteRow
  constructor: (@graph, @dia, @song, @zoomInX, @noteUris, @rowIndex, @selection) ->
    @graph.runHandler(@update.bind(@), "row notes #{@rowIndex}")

  observers: [
    'observedUpdate(graph, song, rowIndex)'
    'onZoom(zoomInX)'
    ]


  observedUpdate: (graph, song, rowIndex) ->
    @update() # old behavior
    #@graph.runHandler(@update.bind(@), "row notes #{@rowIndex}")

  update: (patch) ->
    U = (x) => @graph.Uri(x)

    notesForThisRow = []
    i = 0
    for n in _.sortBy(@graph.objects(@song, U(':note')), 'uri')
      if (i % ROW_COUNT) == @rowIndex
        notesForThisRow.push(n)
      i++

    for newUri in notesForThisRow
      #should only make new ones
      child = new Note(@graph, @selection, @dia, newUri, @setAdjuster, @song, @zoomInX)

  onZoom: ->
    for e in @children
      e.zoomInX = @zoomInX

class Note
  constructor: (@graph, @selection, @dia, @uri, @setAdjuster, @song, @zoomInX)->0
  @is: 'light9-timeline-note'
  @behaviors: [ Polymer.IronResizableBehavior ]
  @listeners: 'iron-resize': 'update' #move to parent elem
  @properties:
    graph: { type: Object, notify: true }
    selection: { type: Object, notify: true }
    dia: { type: Object, notify: true }
    uri: { type: String, notify: true }
    zoomInX: { type: Object, notify: true }
    setAdjuster: {type: Function, notify: true }
    inlineRect: { type: Object, notify: true }
    song: { type: String, notify: true }
  @observers: [
    'onUri(graph, dia, uri, zoomInX, setAdjuster, song)'
    'update(graph, dia, uri, zoomInX, setAdjuster, song)'
    ]
  ready: ->
    @adjusterIds = {} # id : true

  detached: ->
    log('detatch', @uri)
    @dia.clearNote(@uri)
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
        if (add.predicate.equals(del.predicate) and del.predicate.equals(@graph.Uri(':time')) and add.subject.equals(del.subject))
          timeEditFor = add.subject
          if @worldPts and timeEditFor not in @pointUris
            return false
    return true
            
  update: (patch) ->
    # update our note DOM and SVG elements based on the graph
    if not @patchCouldAffectMe(patch)
      # as autodep still fires all handlers on all patches, we just
      # need any single dep to cause another callback. (without this,
      # we would no longer be registered at all)
      @graph.subjects(@uri, @uri, @uri)
      return
    if @isDetached?
      return

    @_updateDisplay()

  _updateDisplay: ->
    U = (x) => @graph.Uri(x)

    # @offsetTop causes some CSS layout to run!
    yForV = (v) => @offsetTop + (1 - v) * @offsetHeight

    originTime = @graph.floatValue(@uri, U(':originTime'))
    effect = @graph.uriValue(@uri, U(':effectClass'))
    for curve in @graph.objects(@uri, U(':curve'))
      if @graph.uriValue(curve, U(':attr')).equals(U(':strength'))

        [@pointUris, @worldPts] = @_getCurvePoints(curve, originTime)
        curveWidthCalc = () => @_curveWidth(@worldPts)
        screenPts = ($V([@zoomInX(pt.e(1)), @offsetTop + (1 - pt.e(2)) * @offsetHeight]) for pt in @worldPts)

        @dia.setNote(@uri, screenPts, effect)
        @_updateAdjusters(screenPts, curveWidthCalc, yForV, U(@song))
        @_updateInlineAttrs(screenPts)
        
    return
  _updateAdjusters: (screenPts, curveWidthCalc, yForV, ctx) ->
    if screenPts[screenPts.length - 1].e(1) - screenPts[0].e(1) < 100
      @clearAdjusters()
    else
      @_makeOffsetAdjuster(yForV, curveWidthCalc, ctx)
      @_makeCurvePointAdjusters(yForV, @worldPts, ctx)
      @_makeFadeAdjusters(yForV, ctx)

  _updateInlineAttrs: (screenPts) ->
    leftX = Math.max(2, screenPts[Math.min(1, screenPts.length - 1)].e(1) + 5)
    rightX = screenPts[Math.min(2, screenPts.length - 1)].e(1) - 5
    if screenPts.length < 3
      rightX = leftX + 120
    w = 250
    h = 110
    wasHidden = @inlineRect?.display == 'none'
    @inlineRect = {
      left: leftX,
      top: @offsetTop + @offsetHeight - h - 5,
      width: w,
      height: h,
      display: if rightX - leftX > w then 'block' else 'none'
      }
    if wasHidden and @inlineRect.display != 'none'
      @async =>
        @querySelector('light9-timeline-note-inline-attrs')?.displayed()
    
  _makeCurvePointAdjusters: (yForV, worldPts, ctx) ->
    for pointNum in [0...worldPts.length]
      @_makePointAdjuster(yForV, worldPts, pointNum, ctx)

  _makePointAdjuster: (yForV, worldPts, pointNum, ctx) ->
    U = (x) => @graph.Uri(x)

    adjId = @uri + '/p' + pointNum
    @adjusterIds[adjId] = true
    @setAdjuster adjId, =>
      adj = new AdjustableFloatObject({
        graph: @graph
        subj: worldPts[pointNum].uri
        pred: U(':time')
        ctx: ctx
        getTargetPosForValue: (value) =>
          $V([@zoomInX(value), yForV(worldPts[pointNum].e(2))])
        getValueForPos: (pos) =>
          origin = @graph.floatValue(@uri, U(':originTime'))
          (@zoomInX.invert(pos.e(1)) - origin)
        getSuggestedTargetOffset: () => @_suggestedOffset(worldPts[pointNum]),
      })
      adj._getValue = (=>
        # note: don't use originTime from the closure- we need the
        # graph dependency
        adj._currentValue + @graph.floatValue(@uri, U(':originTime'))
        )
      adj

  _makeOffsetAdjuster: (yForV, curveWidthCalc, ctx) ->
    U = (x) => @graph.Uri(x)

    adjId = @uri + '/offset'
    @adjusterIds[adjId] = true
    @setAdjuster adjId, => 
      adj = new AdjustableFloatObject({
        graph: @graph
        subj: @uri
        pred: U(':originTime')
        ctx: ctx
        getDisplayValue: (v, dv) => "o=#{dv}"
        getTargetPosForValue: (value) =>
          # display bug: should be working from pt[0].t, not from origin
          $V([@zoomInX(value + curveWidthCalc() / 2), yForV(.5)])
        getValueForPos: (pos) =>
          @zoomInX.invert(pos.e(1)) - curveWidthCalc() / 2
        getSuggestedTargetOffset: () => $V([-10, 0])
      })
      adj

  _makeFadeAdjusters: (yForV, ctx) ->
    @_makeFadeAdjuster(yForV, ctx, @uri + '/fadeIn', 0, 1, $V([-50, -10]))
    n = @worldPts.length
    @_makeFadeAdjuster(yForV, ctx, @uri + '/fadeOut', n - 2, n - 1, $V([50, -10]))

  _makeFadeAdjuster: (yForV, ctx, adjId, i0, i1, offset) ->
    @adjusterIds[adjId] = true
    @setAdjuster adjId, => new AdjustableFade(yForV, i0, i1, @, offset, ctx)
    
  _suggestedOffset: (pt) ->
    if pt.e(2) > .5
      $V([0, 30])
    else
      $V([0, -30])
    
  
  
class DiagramLayer extends Polymer.Element
  # note boxes. 
  @is: 'light9-timeline-diagram-layer'
  @properties: {
    selection: {type: Object, notify: true}
  }
  connectedCallback: ->
    super.connectedCallback()
    @elemById = {}

  setTimeAxis: (width, yTop, scale) ->
    pxPerTick = 50
    axis = d3.axisTop(scale).ticks(width / pxPerTick)
    d3.select(@$.timeAxis).attr('transform', 'translate(0,'+yTop+')').call(axis)

  getOrCreateElem: (uri, groupId, tag, attrs, moreBuild) ->
    elem = @elemById[uri]
    if !elem
      elem = @elemById[uri] = document.createElementNS("http://www.w3.org/2000/svg", tag)
      @$[groupId].appendChild(elem)
      elem.setAttribute('id', uri)
      for k,v of attrs
        elem.setAttribute(k, v)
      if moreBuild
        moreBuild(elem)
    return elem

  _clearElem: (uri, suffixes) ->
    for suff in suffixes
      elem = @elemById[uri+suff]
      if elem
        ko.removeNode(elem)
        delete @elemById[uri+suff]

  _anyPointsInView: (pts) ->
    for pt in pts
      # wrong:
      if pt.e(1) > -100 && pt.e(1) < 2500
        return true
    return false
    
  setNote: (uri, curvePts, effect) ->
    @debounce("setNote #{uri}", () => @_setNoteThrottle(uri, curvePts, effect))
    
  _setNoteThrottle: (uri, curvePts, effect) ->
    areaId = uri + '/area'
    if not @_anyPointsInView(curvePts)
      @clearNote(uri)
      return

    attrs = @_noteAttrs(effect)
    elem = @getOrCreateElem areaId, 'notes', 'path', attrs, (elem) =>
      @_addNoteListeners(elem, uri)
    elem.setAttribute('d', Drawing.svgPathFromPoints(curvePts))
    @_updateNotePathClasses(uri, elem)

  _addNoteListeners: (elem, uri) ->
    elem.addEventListener 'mouseenter', =>
      @selection.hover(uri)
    elem.addEventListener 'mousedown', (ev) =>
      sel = @selection.selected()
      if ev.getModifierState('Control')
        if uri in sel
          sel = _.without(sel, uri)
        else
          sel.push(uri)
      else
        sel = [uri]
      @selection.selected(sel)
    elem.addEventListener 'mouseleave', =>
      @selection.hover(null)

  _noteAttrs: (effect) ->
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

    {style: "fill:hsla(#{hue}, #{sat}%, 58%, 0.313);"}

  clearNote: (uri) ->
    @_clearElem(uri, ['/area'])

  _noteInDiagram: (uri) ->
    return !!@elemById[uri + '/area']

  _updateNotePathClasses: (uri, elem) ->
    ko.computed =>
      return if not @_noteInDiagram(uri)
      classes = 'light9-timeline-diagram-layer ' + (if @selection.hover() == uri then 'hover' else '') + ' '  + (if uri in @selection.selected() then 'selected' else '')
      elem.setAttribute('class', classes)
    
    #elem = @getOrCreateElem(uri+'/label', 'noteLabels', 'text', {style: "font-size:13px;line-height:125%;font-family:'Verana Sans';text-align:start;text-anchor:start;fill:#000000;"})
    #elem.setAttribute('x', curvePts[0].e(1)+20)
    #elem.setAttribute('y', curvePts[0].e(2)-10)
    #elem.innerHTML = effectLabel;
customElements.define(DiagramLayer.is, DiagramLayer)