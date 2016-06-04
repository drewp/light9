log = console.log

class Adjustable
  # Some value you can edit in the UI, probably by dragging stuff. May
  # have a <light9-timeline-adjuster> associated. This object does the
  # layout and positioning.
  #
  # The way dragging should work is that you start in the yellow *adj
  # widget*, wherever it is, but your drag is moving the *target*. The
  # adj will travel around too, but it may do extra moves to not bump
  # into stuff or to get out from under your finger.

  constructor: (@config) ->
    # config has:
    #   getTarget -> vec2 of current target position
    #   getSuggestedTargetOffset -> vec2 pixel offset from target
    #   emptyBox -> true if you want no value display

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

class window.AdjustableFloatObservable extends Adjustable
  constructor: (@config) ->
    # config also has:
    #   observable -> ko.observable we will read and write
    #   getValueForPos(pos) -> what should we set to if the user
    #                          moves target to this coord?

  _getValue: () ->
    @config.observable()

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

class window.AdjustableFloatObject extends Adjustable
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
