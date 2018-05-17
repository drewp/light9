log = console.log
Drawing = window.Drawing


coffeeElementSetup(class AdjustersCanvas extends Polymer.mixinBehaviors([Polymer.IronResizableBehavior], Polymer.Element)
  @is: 'light9-adjusters-canvas'
  @getter_properties:
    setAdjuster: {type: Function, notify: true }
  @getter_observers: [
    'updateAllCoords(adjs)'
  ]
  constructor: ->
    super()
    @redraw = _.throttle(@_throttledRedraw.bind(@), 30, {leading: false})
    @adjs = {}
    
  ready: ->
    super.ready()
    @addEventListener('iron-resize', @resizeUpdate.bind(@))
    @ctx = @$.canvas.getContext('2d')
    
    @redraw()
    @setAdjuster = @_setAdjuster.bind(@)

    @addEventListener('mousedown', @onDown.bind(@))
    @addEventListener('mousemove', @onMove.bind(@))
    @addEventListener('mouseup', @onUp.bind(@))
   
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
    if not nearest? or nearest.distanceFrom(pt) > 50
      return null
    return nearest?.adj

  resizeUpdate: (ev) ->
    @$.canvas.width = ev.target.offsetWidth
    @$.canvas.height = ev.target.offsetHeight
    @redraw()

  _throttledRedraw: () ->
    return unless @ctx?
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
      for tries in [0...4]
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