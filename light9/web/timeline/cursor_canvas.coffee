coffeeElementSetup(class CursorCanvas extends Polymer.mixinBehaviors([Polymer.IronResizableBehavior], Polymer.Element)
  @is: 'light9-cursor-canvas'
  @getter_properties:
    viewState: { type: Object, notify: true, observer: "onViewState" }
  ready: ->
    super.ready()
    @mouseX = 0
    @mouseY = 0
    @cursorPath = null
    @ctx = @$.canvas.getContext('2d')
    @onResize()
    @addEventListener('iron-resize', @onResize.bind(@))

  onViewState: ->
    ko.computed(@redrawCursor.bind(@))

  onResize: (ev) ->
    @$.canvas.width = @offsetWidth
    @$.canvas.height = @offsetHeight
    @redrawCursor()

  redrawCursor: ->
    vs = @viewState
    dependOn = [vs.zoomSpec.t1(), vs.zoomSpec.t2()]
    xZoomedOut = vs.fullZoomX(vs.latestMouseTime())
    xZoomedIn = vs.mouse.pos().e(1)

    @cursorPath = {
      top0: $V([xZoomedOut, vs.audioY()])
      top1: $V([xZoomedOut, vs.audioY() + vs.audioH()])
      mid0: $V([xZoomedIn + 2, vs.zoomedTimeY() + vs.zoomedTimeH()])
      mid1: $V([xZoomedIn - 2, vs.zoomedTimeY() + vs.zoomedTimeH()])
      mid2: $V([xZoomedOut - 1, vs.audioY() + vs.audioH()])
      mid3: $V([xZoomedOut + 1, vs.audioY() + vs.audioH()])
      bot0: $V([xZoomedIn, vs.zoomedTimeY() + vs.zoomedTimeH()])
      bot1: $V([xZoomedIn, @offsetHeight])
    }
    @redraw()

  redraw: ->
    return unless @ctx
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
)