
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

  setCursor: (y1, h1, y2, h2, viewState) ->
    
    xZoomedOut = viewState.fullZoomX(viewState.latestMouseTime())
    xZoomedIn = viewState.mouse.pos().e(1)

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
    Drawing.line(@ctx, $V([0, @mouseY]), $V([@$.canvas.width, @mouseY]))
    Drawing.line(@ctx, $V([@mouseX, 0]), $V([@mouseX, @$.canvas.height]))
    @ctx.stroke()

    if @cursorPath
      @ctx.strokeStyle = '#ff0303'
      @ctx.lineWidth = 1.5
      @ctx.beginPath()
      Drawing.line(@ctx, @cursorPath.top0, @cursorPath.top1)
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
      Drawing.line(@ctx, @cursorPath.bot0, @cursorPath.bot1, '#ff0303', '3px')
      @ctx.stroke()
    