log = console.log
Drawing = window.Drawing

maxDist = 60

coffeeElementSetup(class AdjustersCanvas extends Polymer.mixinBehaviors([Polymer.IronResizableBehavior], Polymer.Element)
  @is: 'light9-adjusters-canvas'
  @getter_properties:
    setAdjuster: {type: Function, notify: true }
  @getter_observers: [
    'updateAllCoords(adjs)'
  ]
  constructor: ->
    super()
    @redraw = _.throttle(@_throttledRedraw.bind(@), 60, {leading: false})
    @adjs = {}
    
  ready: ->
    super.ready()
    @addEventListener('iron-resize', @resizeUpdate.bind(@))
    @ctx = @$.canvas.getContext('2d')
    
    @redraw()
    @setAdjuster = @_setAdjuster.bind(@)

    # These don't fire; TimelineEditor calls the handlers for us.
    @addEventListener('mousedown', @onDown.bind(@))
    @addEventListener('mousemove', @onMove.bind(@))
    @addEventListener('mouseup', @onUp.bind(@))
   
  onDown: (ev) ->
    if ev.buttons == 1
      start = $V([ev.x, ev.y])
      adj = @_adjAtPoint(start)
      if adj
        ev.stopPropagation()
        @currentDrag = {start: start, adj: adj}
        adj.startDrag()

  onMove: (ev) ->
    pos = $V([ev.x, ev.y])
    if @currentDrag
      @currentDrag.cur = pos
      @currentDrag.adj.continueDrag(
        @currentDrag.cur.subtract(@currentDrag.start))

  onUp: (ev) ->
    return unless @currentDrag
    @currentDrag.adj.endDrag()
    @currentDrag = null
    
  _setAdjuster: (adjId, makeAdjustable) ->
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
    if nearest?
      log('near', nearest.distanceFrom(pt))
    if not nearest? or nearest.distanceFrom(pt) > maxDist
      return null
    return nearest?.adj

  resizeUpdate: (ev) ->
    @$.canvas.width = ev.target.offsetWidth
    @$.canvas.height = ev.target.offsetHeight
    @canvasCenter = $V([@$.canvas.width / 2, @$.canvas.height / 2])
    @redraw()

  _throttledRedraw: () ->
    return unless @ctx?
    console.time('adjs redraw')
    @_layoutCenters()
    
    @ctx.clearRect(0, 0, @$.canvas.width, @$.canvas.height)

    for adjId, adj of @adjs
      ctr = adj.getHandle()
      target = adj.getTarget()
      if target.e(1) < 0 or target.e(1) > @$.canvas.width or target.e(2) < 0 or target.e(2) > @$.canvas.height
        continue
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
      adj.handle = adj.getSuggestedHandle()
      
    for tries in [0...5]
      for _, adj of @adjs
        current = adj.handle
        @qt.remove(current)
        nearest = @qt.find(current.e(1), current.e(2), maxDist)
        if nearest
          dist = current.distanceFrom(nearest)
          if dist < maxDist
            away = current.subtract(nearest).toUnitVector()
            toScreenCenter = @canvasCenter.subtract(current).toUnitVector()
            current = current.add(away.x(20).add(toScreenCenter.x(2)))
            marg = 10
            current = $V([Math.max(marg, Math.min(@$.canvas.width - marg, current.e(1))),
                         Math.max(marg, Math.min(@$.canvas.height - marg, current.e(2)))])
            adj.handle = current
        current.adj = adj
        @qt.add(current)

      #if -50 < output.e(1) < 20 # mostly for zoom-left
      #  output.setElements([
      #    Math.max(20, output.e(1)),
      #    output.e(2)])
        
  _drawConnector: (ctr, target) ->
    @ctx.strokeStyle = '#aaa'
    @ctx.lineWidth = 2
    @ctx.beginPath()
    Drawing.line(@ctx, ctr, target)
    @ctx.stroke()
    
  _drawAdjuster: (label, x1, y1, x2, y2) ->
    radius = 8

    @ctx.shadowColor = 'black'
    @ctx.shadowBlur = 15
    @ctx.shadowOffsetX = 5
    @ctx.shadowOffsetY = 9
    
    @ctx.fillStyle = 'rgba(255, 255, 0, 0.5)'
    @ctx.beginPath()
    Drawing.roundRect(@ctx, x1, y1, x2, y2, radius)
    @ctx.fill()

    @ctx.shadowColor = 'rgba(0,0,0,0)'
        
    @ctx.strokeStyle = 'yellow'
    @ctx.lineWidth = 2
    @ctx.setLineDash([3, 3])
    @ctx.beginPath()
    Drawing.roundRect(@ctx, x1, y1, x2, y2, radius)
    @ctx.stroke()
    @ctx.setLineDash([])

    @ctx.font = "12px sans"
    @ctx.fillStyle = '#000'
    @ctx.fillText(label, x1 + 5, y2 - 5, x2 - x1 - 10)

    # coords from a center that's passed in
    # # special layout for the thaeter ones with middinh
    # l/r arrows
    # mouse arrow cursor upon hover, and accent the hovered adjuster
    # connector
)