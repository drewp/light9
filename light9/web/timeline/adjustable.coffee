log = console.log

class Adjustable
  # Some value you can edit in the UI, probably by dragging
  # stuff. Drawn by light9-adjusters-canvas. This object does the
  # layout and positioning.
  #
  # The way dragging should work is that you start in the yellow *adj
  # widget*, wherever it is, but your drag is moving the *target*. The
  # adj will travel around too, but it may do extra moves to not bump
  # into stuff or to get out from under your finger.

  constructor: (@config) ->
    @ctor2()

  ctor2: () ->
    # config has:
    #   getTarget -> vec2 of current target position
    #   getSuggestedTargetOffset -> vec2 pixel offset from target
    #   emptyBox -> true if you want no value display

    # updated later by layout algoritm
    @centerOffset = $V([0, 0])

  getDisplayValue: () ->
    return '' if @config.emptyBox
    defaultFormat = d3.format(".4g")(@_getValue())
    if @config.getDisplayValue?
      return @config.getDisplayValue(@_getValue(), defaultFormat)
    defaultFormat

  getSuggestedCenter: () ->
    @getTarget().add(@config.getSuggestedTargetOffset())

  getCenter: () -> # vec2 of pixels
    @getTarget().add(@centerOffset)

  getTarget: () -> # vec2 of pixels
    @config.getTarget()

  subscribe: (onChange) ->
    # change could be displayValue or center or target. This likely
    # calls onChange right away if there's any data yet.
    throw new Error('not implemented')

  startDrag: () ->
    @initialTarget = @getTarget()

  continueDrag: (pos) ->
    ## pos is vec2 of pixels relative to the drag start
    @targetDraggedTo = pos.add(@initialTarget)

  endDrag: () ->
    # override

  _editorCoordinates: () -> # vec2 of mouse relative to <l9-t-editor>
    return @targetDraggedTo
    ev = d3.event.sourceEvent

    if ev.target.tagName == "LIGHT9-TIMELINE-EDITOR"
      rootElem = ev.target
    else
      rootElem = ev.target.closest('light9-timeline-editor')

    if ev.touches?.length
      ev = ev.touches[0]

    # storing root on the object to remember it across calls in case
    # you drag outside the editor.
    @root = rootElem.getBoundingClientRect() if rootElem
    offsetParentPos = $V([ev.pageX - @root.left, ev.pageY - @root.top])

    return offsetParentPos

class window.AdjustableFloatObservable extends Adjustable
  constructor: (@config) ->
    # config also has:
    #   observable -> ko.observable we will read and write
    #   getValueForPos(pos) -> what should we set to if the user
    #                          moves target to this coord?
    super()
    @ctor2()

  _getValue: () ->
    @config.observable()

  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start.
    super(pos)
    epos = @_editorCoordinates()
    newValue = @config.getValueForPos(epos)
    @config.observable(newValue)

  subscribe: (onChange) ->
    log('AdjustableFloatObservable subscribe', @config)
    ko.computed =>
      @config.observable()
      onChange()

class window.AdjustableFloatObject extends Adjustable
  constructor: (@config) ->
    # config also has:
    #   graph
    #   subj
    #   pred
    #   ctx
    #   getTargetPosForValue(value) -> getTarget result for value
    #   getValueForPos
    super()
    @ctor2()
    if not @config.ctx?
      throw new Error("missing ctx")
    @config.graph.runHandler(@_syncValue.bind(@),
                             "adj sync #{@config.subj.value}")

  _syncValue: () ->
    @_currentValue = @config.graph.floatValue(@config.subj, @config.pred)
    @_onChange() if @_onChange

  _getValue: () ->
    # this is a big speedup- callers use _getValue about 4x as much as
    # the graph changes and graph.floatValue is slow
    @_currentValue

  getTarget: () ->
    @config.getTargetPosForValue(@_getValue())

  subscribe: (onChange) ->
    # only works on one subscription at a time
    throw new Error('multi subscribe not implemented') if @_onChange
    @_onChange = onChange

  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start
    super(pos)
    newValue = @config.getValueForPos(@_editorCoordinates())

    @config.graph.patchObject(@config.subj, @config.pred,
                              @config.graph.LiteralRoundedFloat(newValue),
                              @config.ctx)

class window.AdjustableFade extends Adjustable
  constructor: (@yForV, @i0, @i1, @note, offset, ctx) ->
    super()
    @config = {
      getSuggestedTargetOffset: -> offset
      getTarget: @getTarget.bind(@)
      ctx: ctx
    }
    @ctor2()

  getTarget: ->
    mid = @note.worldPts[@i0].x(.5).add(@note.worldPts[@i1].x(.5))
    $V([@note.zoomInX(mid.e(1)), @yForV(mid.e(2))])

  _getValue: ->
    mid = @note.worldPts[@i0].x(.5).add(@note.worldPts[@i1].x(.5))
    mid.e(1)

  continueDrag: (pos) ->
    # pos is vec2 of pixels relative to the drag start
    super(pos)
    graph = @note.graph
    U = (x) -> graph.Uri(x)

    goalCenterSec = @note.zoomInX.invert(@initialTarget.e(1) + pos.e(1))

    diamSec = @note.worldPts[@i1].e(1) - @note.worldPts[@i0].e(1)
    newSec0 = goalCenterSec - diamSec / 2
    newSec1 = goalCenterSec + diamSec / 2

    originSec = graph.floatValue(@note.uri, U(':originTime'))

    p0 = @_makePatch(graph, @i0, newSec0, originSec, @config.ctx)
    p1 = @_makePatch(graph, @i1, newSec1, originSec, @config.ctx)

    graph.applyAndSendPatch(@_addPatches(p0, p1))

  _makePatch: (graph, idx, newSec, originSec, ctx) ->
    graph.getObjectPatch(@note.worldPts[idx].uri,
                         graph.Uri(':time'),
                         graph.LiteralRoundedFloat(newSec - originSec), ctx)

  _addPatches: (p0, p1) ->
    {
      addQuads: p0.addQuads.concat(p1.addQuads),
      delQuads: p0.delQuads.concat(p1.delQuads)
    }