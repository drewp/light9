log = console.log
Drawing = window.Drawing
ROW_COUNT = 7

class Project
  constructor: (@graph) ->

  makeEffect: (uri) ->
    U = (x) => @graph.Uri(x)
    effect = U(uri.value + '/effect')
    quad = (s, p, o) => @graph.Quad(s, p, o, effect)

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

  makeNewNote: (song, effect, dropTime, desiredWidthT) ->
    U = (x) => @graph.Uri(x)
    quad = (s, p, o) => @graph.Quad(s, p, o, song)

    newNote = @graph.nextNumberedResource("#{song.value}/n")
    newCurve = @graph.nextNumberedResource("#{newNote.value}c")
    points = @graph.nextNumberedResources("#{newCurve.value}p", 4)

    curveQuads = [
        quad(song, U(':note'), newNote)
        quad(newNote, U('rdf:type'), U(':Note'))
        quad(newNote, U(':originTime'), @graph.LiteralRoundedFloat(dropTime))
        quad(newNote, U(':effectClass'), effect)
        quad(newNote, U(':curve'), newCurve)
        quad(newCurve, U('rdf:type'), U(':Curve'))
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
    patch = {delQuads: [@graph.Quad(song, graph.Uri(':note'), note, song)], addQuads: []}
    @graph.applyAndSendPatch(patch)
    if note in selection.selected()
      selection.selected(_.without(selection.selected(), note))


coffeeElementSetup(class TimelineEditor extends Polymer.mixinBehaviors([Polymer.IronResizableBehavior], Polymer.Element)
  @is: 'light9-timeline-editor'
  @getter_properties:
    viewState: { type: Object }
    debug: {type: String}
    graph: {type: Object, notify: true}
    project: {type: Object}
    setAdjuster: {type: Function, notify: true}
    playerSong: {type: String, notify: true}
    followPlayerSong: {type: Boolean, notify: true, value: true}
    song: {type: String, notify: true}
    show: {type: String, notify: true}
    songTime: {type: Number, notify: true}
    songDuration: {type: Number, notify: true}
    songPlaying: {type: Boolean, notify: true}
    selection: {type: Object, notify: true}
  @getter_observers: [
    '_onSong(playerSong, followPlayerSong)',
    '_onGraph(graph)',
    '_onSongDuration(songDuration, viewState)',
    '_onSongTime(songTime, viewState)',
    '_onSetAdjuster(setAdjuster)',
  ]
  constructor: ->
    super()
    @viewState = new ViewState()
    window.viewState = @viewState

  ready: ->
    super.ready()
    @addEventListener 'mousedown', (ev) => @$.adjustersCanvas.onDown(ev)
    @addEventListener 'mousemove', (ev) => @$.adjustersCanvas.onMove(ev)
    @addEventListener 'mouseup', (ev) => @$.adjustersCanvas.onUp(ev)

    ko.options.deferUpdates = true

    @selection = {hover: ko.observable(null), selected: ko.observable([])}

    window.debug_zoomOrLayoutChangedCount = 0
    window.debug_adjUpdateDisplay = 0

    ko.computed(@zoomOrLayoutChanged.bind(@))

    @trackMouse()
    @bindKeys()
    @bindWheelZoom(@)

    setInterval(@updateDebugSummary.bind(@), 100)

    @addEventListener('iron-resize', @_onIronResize.bind(@))
    Polymer.RenderStatus.afterNextRender(this, @_onIronResize.bind(@))

    Polymer.RenderStatus.afterNextRender this, =>
      setupDrop(@$.zoomed.$.rows, @$.zoomed.$.rows, @, @$.zoomed.onDrop.bind(@$.zoomed))

  _onIronResize: ->
    @viewState.setWidth(@offsetWidth)
    @viewState.coveredByDiagramTop(@$.coveredByDiagram.offsetTop)
    @viewState.rowsY(@$.zoomed.$.rows.offsetTop) if @$.zoomed?.$?.rows?
    @viewState.audioY(@$.audio.offsetTop)
    @viewState.audioH(@$.audio.offsetHeight)
    if @$.zoomed?.$?.time?
      @viewState.zoomedTimeY(@$.zoomed.$.time.offsetTop)
      @viewState.zoomedTimeH(@$.zoomed.$.time.offsetHeight)

  _onSongTime: (t) ->
    @viewState.cursor.t(t)

  _onSongDuration: (d) ->
    d = 700 if d < 1 # bug is that asco isn't giving duration, but 0 makes the scale corrupt
    @viewState.zoomSpec.duration(d)

  _onSong: (s) ->
    @song = @playerSong if @followPlayerSong

  _onGraph: (graph) ->
    @project = new Project(graph)
    @show = 'http://light9.bigasterisk.com/show/dance2019'

  _onSetAdjuster: () ->
    @makeZoomAdjs()

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
    dependOn = [vs.zoomSpec.t1(), vs.zoomSpec.t2(), vs.width()]

    # shouldn't need this- deps should get it
    @$.zoomed.gatherNotes() if @$.zoomed?.gatherNotes?

    # todo: these run a lot of work purely for a time change
    if @$.zoomed?.$?.audio?
      #@dia.setTimeAxis(vs.width(), @$.zoomed.$.audio.offsetTop, vs.zoomInX)
      @$.adjustersCanvas.updateAllCoords()

  trackMouse: ->
    # not just for show- we use the mouse pos sometimes
    for evName in ['mousemove', 'touchmove']
      @addEventListener evName, (ev) =>
        ev.preventDefault()

        # todo: consolidate with _editorCoordinates version
        if ev.touches?.length
          ev = ev.touches[0]

        root = @$.cursorCanvas.getBoundingClientRect()
        @viewState.mouse.pos($V([ev.pageX - root.left, ev.pageY - root.top]))

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

  bindKeys: ->
    shortcut.add "Ctrl+P", (ev) =>
      @$.music.seekPlayOrPause(@viewState.latestMouseTime())
    shortcut.add "Ctrl+Escape", => @viewState.frameAll()
    shortcut.add "Shift+Escape", => @viewState.frameToEnd()
    shortcut.add "Escape", => @viewState.frameCursor()
    shortcut.add "L", =>
      @$.adjustersCanvas.updateAllCoords()
    shortcut.add 'Delete', =>
      for note in @selection.selected()
        @project.deleteNote(@graph.Uri(@song), note, @selection)

  makeZoomAdjs: ->
    yMid = => @$.audio.offsetTop + @$.audio.offsetHeight / 2

    valForPos = (pos) =>
      x = pos.e(1)
      t = @viewState.fullZoomX.invert(x)
    @setAdjuster('zoom-left', => new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t1,
      getTarget: () =>
        $V([@viewState.fullZoomX(@viewState.zoomSpec.t1()), yMid()])
      getSuggestedTargetOffset: () => $V([-50, 10])
      getValueForPos: valForPos
    }))

    @setAdjuster('zoom-right', => new AdjustableFloatObservable({
      observable: @viewState.zoomSpec.t2,
      getTarget: () =>
        $V([@viewState.fullZoomX(@viewState.zoomSpec.t2()), yMid()])
      getSuggestedTargetOffset: () => $V([50, 10])
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
      getTarget: () => $V([@viewState.fullZoomX(panObs()), yMid()])
      getSuggestedTargetOffset: () => $V([0, 0])
      getValueForPos: valForPos
    }))
)


# plan: in here, turn all the notes into simple js objects with all
# their timing data and whatever's needed for adjusters. From that, do
# the brick layout. update only changing adjusters.
coffeeElementSetup(class TimeZoomed extends Polymer.mixinBehaviors([Polymer.IronResizableBehavior], Polymer.Element)
  @is: 'light9-timeline-time-zoomed'
  @getter_properties:
    graph: { type: Object, notify: true }
    project: { type: Object }
    selection: { type: Object, notify: true }
    song: { type: String, notify: true }
    viewState: { type: Object, notify: true }
    inlineAttrConfigs: { type: Array, value: [] } # only for inlineattrs that should be displayed
  @getter_observers: [
    '_onGraph(graph, setAdjuster, song, viewState, project)',
    'onZoom(viewState)',
    '_onViewState(viewState)',
  ]
  constructor: ->
    super()
    @numRows = 6
    @noteByUriStr = new Map()
    @stage = new PIXI.Container()
    @stage.interactive=true

    @renderer = PIXI.autoDetectRenderer({
      backgroundColor: 0x606060,
      antialias: true,
      forceCanvas: true,
    })
    @bg = new PIXI.Container()
    @stage.addChild(@bg)

    @dirty = _.debounce(@_repaint.bind(@), 10)

  ready: ->
    super.ready()

    @addEventListener('iron-resize', @_onResize.bind(@))
    Polymer.RenderStatus.afterNextRender(this, @_onResize.bind(@))

    @$.rows.appendChild(@renderer.view)

    # This works for display, but pixi hit events didn't correctly
    # move with the objects, so as a workaround, I extended the top of
    # the canvas in _onResize.
    #
    #ko.computed =>
    #  @stage.setTransform(0, -(@viewState.rowsY()), 1, 1, 0, 0, 0, 0, 0)

  _onResize: ->
    @$.rows.firstChild.style.position = 'relative'
    @$.rows.firstChild.style.top = -@viewState.rowsY() + 'px'

    @renderer.resize(@clientWidth, @clientHeight + @viewState.rowsY())

    @dirty()

  _onGraph: (graph, setAdjuster, song, viewState, project)->
    return unless @song # polymer will call again
    @graph.runHandler(@gatherNotes.bind(@), 'zoom notes')

  _onViewState: (viewState) ->
    @brickLayout = new BrickLayout(@viewState, @numRows)

  noteDirty: -> @dirty()
    
  onZoom: ->
    updateZoomFlattened = ->
      @zoomFlattened = ko.toJS(@viewState.zoomSpec)
    ko.computed(updateZoomFlattened.bind(@))

  gatherNotes: ->
    U = (x) => @graph.Uri(x)
    return unless @song?
    songNotes = @graph.objects(U(@song), U(':note'))

    toRemove = new Set(@noteByUriStr.keys())
    
    for uri in @graph.sortedUris(songNotes)
      had = toRemove.delete(uri.value)
      if not had
        @_addNote(uri)

    toRemove.forEach @_delNote.bind(@)

    @dirty()

  isActiveNote: (note) -> @noteByUriStr.has(note.value)

  _repaint: ->
    @_drawGrid()  
    @renderer.render(@stage)

  _drawGrid: ->
    # maybe someday this has snappable timing markers too
    @bg.removeChildren()
    gfx = new PIXI.Graphics()
    @bg.addChild(gfx)

    gfx.lineStyle(1, 0x222222, 1)
    for row in [0...@numRows]
      y = @brickLayout.rowBottom(row)
      gfx.moveTo(0, y)
      gfx.lineTo(@clientWidth, y)

  _addNote: (uri) ->
    U = (x) => @graph.Uri(x)
    
    con = new PIXI.Container()
    con.interactive=true
    @stage.addChild(con)
    
    note = new Note(@, con, @project, @graph, @selection, uri, @setAdjuster, U(@song), @viewState, @brickLayout)
    # this must come before the first Note.draw
    @noteByUriStr.set(uri.value, note)
    @brickLayout.addNote(note, note.onRowChange.bind(note))
    note.initWatchers()

  _delNote: (uriStr) ->
    n = @noteByUriStr.get(uriStr)
    @brickLayout.delNote(n)
    @stage.removeChild(n.container)
    n.destroy()
    @noteByUriStr.delete(uriStr)
            
  onDrop: (effect, pos) ->
    U = (x) => @graph.Uri(x)

    return unless effect and effect.match(/^http/)

    # we could probably accept some initial overrides right on the
    # effect uri, maybe as query params

    if not @graph.contains(effect, U('rdf:type'), U(':Effect'))
      if @graph.contains(effect, U('rdf:type'), U(':LightSample'))
        effect = @project.makeEffect(effect)
      else
        log("drop #{effect} is not an effect")
        return

    dropTime = @viewState.zoomInX.invert(pos.e(1))

    desiredWidthX = @offsetWidth * .3
    desiredWidthT = @viewState.zoomInX.invert(desiredWidthX) - @viewState.zoomInX.invert(0)
    desiredWidthT = Math.min(desiredWidthT, @viewState.zoomSpec.duration() - dropTime)
    @project.makeNewNote(U(@song), U(effect), dropTime, desiredWidthT)

  updateInlineAttrs: (note, config) ->
    if not config?
      index = 0
      for c in @inlineAttrConfigs
        if c.uri.equals(note)
          @splice('inlineAttrConfigs', index)
          return
        index += 1
    else
      index = 0
      for c in @inlineAttrConfigs
        if c.uri.equals(note)
          @splice('inlineAttrConfigs', index, 1, config)
          return
        index += 1
      @push('inlineAttrConfigs', config)
)



coffeeElementSetup(class TimeAxis extends Polymer.Element
  @is: "light9-timeline-time-axis",
  @getter_properties:
    viewState: { type: Object, notify: true, observer: "onViewState" }
  onViewState: ->
    ko.computed =>
      dependOn = [@viewState.zoomSpec.t1(), @viewState.zoomSpec.t2()]
      pxPerTick = 50
      axis = d3.axisTop(@viewState.zoomInX).ticks(@viewState.width() / pxPerTick)
      d3.select(@$.axis).call(axis)
)


# Maintains a pixi object, some adjusters, and inlineattrs corresponding to a note
# in the graph.
class Note
  constructor: (@parentElem, @container, @project, @graph, @selection, @uri, @setAdjuster, @song, @viewState, @brickLayout) ->
    @adjusterIds = new Set() # id string
    @updateSoon = _.debounce(@update.bind(@), 30)

  initWatchers: ->
    @graph.runHandler(@update.bind(@), "note update #{@uri.value}")
    ko.computed @update.bind(@)

  destroy: ->
    log('destroy', @uri.value)
    @isDetached = true
    @clearAdjusters()
    @parentElem.updateInlineAttrs(@uri, null)

  clearAdjusters: ->
    @adjusterIds.forEach (i) =>
      @setAdjuster(i, null)
    @adjusterIds.clear()

  getCurvePoints: (subj, curveAttr) ->
    U = (x) => @graph.Uri(x)
    originTime = @graph.floatValue(subj, U(':originTime'))

    for curve in @graph.objects(subj, U(':curve'))
      if @graph.uriValue(curve, U(':attr')).equals(curveAttr)
        return @project.getCurvePoints(curve, originTime)
    throw new Error("curve #{@uri.value} has no attr #{curveAttr.value}")

  midPoint: (i0, i1) ->
    p0 = @worldPts[i0]
    p1 = @worldPts[i1]
    p0.x(.5).add(p1.x(.5))

  _planDrawing: ->
    U = (x) => @graph.Uri(x)
    [pointUris, worldPts] = @getCurvePoints(@uri, U(':strength'))
    effect = @graph.uriValue(@uri, U(':effectClass'))

    yForV = @brickLayout.yForVFor(@)
    dependOn = [@viewState.zoomSpec.t1(),
                @viewState.zoomSpec.t2(),
                @viewState.width()]
    screenPts = (new PIXI.Point(@viewState.zoomInX(pt.e(1)),
                                yForV(pt.e(2))) for pt in worldPts)
    return {
      yForV: yForV
      worldPts: worldPts
      screenPts: screenPts
      effect: effect
      hover: @uri.equals(@selection.hover())
      selected: @selection.selected().filter((s) => s.equals(@uri)).length
    }

  onRowChange: ->
    @clearAdjusters()
    @updateSoon()

  redraw: (params) ->
    # no observable or graph deps in here
    @container.removeChildren()
    @graphics = new PIXI.Graphics({nativeLines: false})
    @graphics.interactive = true
    @container.addChild(@graphics)

    if params.hover
      @_traceBorder(params.screenPts, 12, 0x888888)
    if params.selected
      @_traceBorder(params.screenPts, 6, 0xff2900)

    shape = new PIXI.Polygon(params.screenPts)
    @graphics.beginFill(@_noteColor(params.effect), .313)
    @graphics.drawShape(shape)
    @graphics.endFill()

    @_traceBorder(params.screenPts, 2, 0xffd900)

    @_addMouseBindings()
    
                 
  update: ->
    if not @parentElem.isActiveNote(@uri)
      # stale redraw call
      return

    if @worldPts
      @brickLayout.setNoteSpan(@, @worldPts[0].e(1),
                               @worldPts[@worldPts.length - 1].e(1))

    params = @_planDrawing()
    @worldPts = params.worldPts

    @redraw(params)

    curveWidthCalc = () => @project.curveWidth(@worldPts)
    @_updateAdjusters(params.screenPts, @worldPts, curveWidthCalc,
                      params.yForV, @viewState.zoomInX, @song)
    @_updateInlineAttrs(params.screenPts, params.yForV)
    @parentElem.noteDirty()

  _traceBorder: (screenPts, thick, color) ->
    @graphics.lineStyle(thick, color, 1)
    @graphics.moveTo(screenPts[0].x, screenPts[0].y)
    for p in screenPts.slice(1)
      @graphics.lineTo(p.x, p.y)

  _addMouseBindings: () ->
    @graphics.on 'mousedown', (ev) =>
      @_onMouseDown(ev)

    @graphics.on 'mouseover', =>
      if @selection.hover() and @selection.hover().equals(@uri)
        # Hovering causes a redraw, which would cause another
        # mouseover event.
        return
      @selection.hover(@uri)

    # mouseout never fires since we rebuild the graphics on mouseover.
    @graphics.on 'mousemove', (ev) =>
      if @selection.hover() and @selection.hover().equals(@uri) and ev.target != @graphics
        @selection.hover(null)

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

  xupdate: (patch) ->
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

  _updateAdjusters: (screenPts, worldPts, curveWidthCalc, yForV, zoomInX, ctx) ->
    # todo: allow offset even on more narrow notes
    if screenPts[screenPts.length - 1].x - screenPts[0].x < 100 or screenPts[0].x > @parentElem.offsetWidth or screenPts[screenPts.length - 1].x < 0
      @clearAdjusters()
    else
      @_makeOffsetAdjuster(yForV, curveWidthCalc, ctx)
      @_makeCurvePointAdjusters(yForV, worldPts, ctx)
      @_makeFadeAdjusters(yForV, zoomInX, ctx, worldPts)

  _updateInlineAttrs: (screenPts, yForV) ->
    w = 280

    leftX = Math.max(2, screenPts[Math.min(1, screenPts.length - 1)].x + 5)
    rightX = screenPts[Math.min(2, screenPts.length - 1)].x - 5
    if screenPts.length < 3
      rightX = leftX + w

    if rightX - leftX < w or rightX < w or leftX > @parentElem.offsetWidth
      @parentElem.updateInlineAttrs(@uri, null)
      return

    config = {
      uri: @uri,
      left: leftX,
      top: yForV(1) + 5,
      width: w,
      height: yForV(0) - yForV(1) - 15,
      }

    @parentElem.updateInlineAttrs(@uri, config)

  _makeCurvePointAdjusters: (yForV, worldPts, ctx) ->
    for pointNum in [0...worldPts.length]
      @_makePointAdjuster(yForV, worldPts, pointNum, ctx)

  _makePointAdjuster: (yForV, worldPts, pointNum, ctx) ->
    U = (x) => @graph.Uri(x)

    adjId = @uri.value + '/p' + pointNum
    @adjusterIds.add(adjId)
    @setAdjuster adjId, =>
      adj = new AdjustableFloatObject({
        graph: @graph
        subj: worldPts[pointNum].uri
        pred: U(':time')
        ctx: ctx
        getTargetPosForValue: (value) =>
          $V([@viewState.zoomInX(value), yForV(worldPts[pointNum].e(2))])
        getValueForPos: (pos) =>
          origin = @graph.floatValue(@uri, U(':originTime'))
          (@viewState.zoomInX.invert(pos.e(1)) - origin)
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

    adjId = @uri.value + '/offset'
    @adjusterIds.add(adjId)
    @setAdjuster adjId, =>
      adj = new AdjustableFloatObject({
        graph: @graph
        subj: @uri
        pred: U(':originTime')
        ctx: ctx
        getDisplayValue: (v, dv) => "o=#{dv}"
        getTargetPosForValue: (value) =>
          # display bug: should be working from pt[0].t, not from origin
          $V([@viewState.zoomInX(value + curveWidthCalc() / 2), yForV(.5)])
        getValueForPos: (pos) =>
          @viewState.zoomInX.invert(pos.e(1)) - curveWidthCalc() / 2
        getSuggestedTargetOffset: () => $V([-10, 0])
      })
      adj

  _makeFadeAdjusters: (yForV, zoomInX, ctx, worldPts) ->
    U = (x) => @graph.Uri(x)
    @_makeFadeAdjuster(yForV, zoomInX, ctx, @uri.value + '/fadeIn', 0, 1, $V([-50, -10]))
    n = worldPts.length
    @_makeFadeAdjuster(yForV, zoomInX, ctx, @uri.value + '/fadeOut', n - 2, n - 1, $V([50, -10]))

  _makeFadeAdjuster: (yForV, zoomInX, ctx, adjId, i0, i1, offset) ->
    @adjusterIds.add(adjId)
    @setAdjuster adjId, =>
      new AdjustableFade(yForV, zoomInX, i0, i1, @, offset, ctx)

  _suggestedOffset: (pt) ->
    if pt.e(2) > .5
      $V([0, 30])
    else
      $V([0, -30])

  _onMouseDown: (ev) ->
    sel = @selection.selected()
    if ev.data.originalEvent.ctrlKey
      if @uri in sel
        sel = _.without(sel, @uri)
      else
        sel.push(@uri)
    else
      sel = [@uri]
    @selection.selected(sel)

  _noteColor: (effect) ->
    effect = effect.value
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

    return parseInt(tinycolor.fromRatio({h: hue / 360, s: sat / 100, l: .58}).toHex(), 16)

    #elem = @getOrCreateElem(uri+'/label', 'noteLabels', 'text', {style: "font-size:13px;line-height:125%;font-family:'Verana Sans';text-align:start;text-anchor:start;fill:#000000;"})
    #elem.setAttribute('x', curvePts[0].e(1)+20)
    #elem.setAttribute('y', curvePts[0].e(2)-10)
    #elem.innerHTML = effectLabel
