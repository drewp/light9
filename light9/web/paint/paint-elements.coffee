class Painting
  constructor: ->
    @strokes = []

  addStroke: (pts, color) ->
    @strokes.push({pts: pts, color: color})

  hover: (pos) ->
    @strokes = [{pts: [pos, [pos[0], pos[1] + .01]], color: "#ffffff"}]

  getDoc: ->
    {strokes: @strokes}

class Stroke
  constructor: (pos, @color, @size) ->
    @path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    @path.setAttributeNS(null, 'd', "M #{pos[0]*@size[0]} #{pos[1]*@size[1]}")
    @pts = [pos]
    @lastPos = pos

  appendElem: (parent) ->
    parent.appendChild(@path)
    
  move: (pos) ->
    if Math.hypot(pos[0] - @lastPos[0], pos[1] - @lastPos[1]) < .02
      return
    @path.attributes.d.value += " L #{pos[0]*@size[0]} #{pos[1]*@size[1]}"
    @pts.push(pos)
    @lastPos = pos

Polymer
  is: "light9-paint-canvas"
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'onResize'
  properties: {
    bg: { type: String },
    tool: { type: String },
    painting: { type: Object } # output
  }
  ready: ->
    @onResize()
    @painting = new Painting()
    @$.paint.addEventListener('mousedown', @onDown.bind(@))
    @$.paint.addEventListener('mousemove', @onMove.bind(@))
    @$.paint.addEventListener('mouseup', @onUp.bind(@))
    @$.paint.addEventListener('touchstart', @onDown.bind(@))
    @$.paint.addEventListener('touchmove', @onMove.bind(@))
    @$.paint.addEventListener('touchend', @onUp.bind(@))

    @hover = _.throttle((ev) =>
          @painting.hover(@evPos(ev))
          @fire('paintingChanged', @painting)
        , 100)


  evPos: (ev) ->
    px = (if ev.touches?.length? then [Math.round(ev.touches[0].clientX),
                                       Math.round(ev.touches[0].clientY)] else [ev.x, ev.y])
    return [px[0] / @size[0], px[1] / @size[1]]

  onDown: (ev) ->
    switch @tool
      when "hover"
        @onMove(ev)
      when "paint"
        # if it's on an existing one, do selection
        @stroke = new Stroke(@evPos(ev), '#aaaaaa', @size)
        @stroke.appendElem(@$.paint)
    @scopeSubtree(@$.paint)

  onMove: (ev) ->
    switch @tool
      when "hover"
        @hover(ev)

      when "paint"
        # ..or move selection
        return unless @stroke
        @stroke.move(@evPos(ev))

  onUp: (ev) ->
    return unless @stroke
    @painting.addStroke(@stroke.pts, @stroke.color)
    @stroke = null
    
    @notifyPath('painting.strokes.length') # not working
    @fire('paintingChanged', @painting)

  onResize: (ev) ->
    @size = [@$.parent.offsetWidth, @$.parent.offsetHeight]
    @$.paint.attributes.viewBox.value = "0 0 #{@size[0]} #{@size[1]}"


Polymer
  is: "light9-simulation"
  properties: {
    layers: { type: Object }
    solution: { type: Object }
  }
  listeners: [
    "onLayers(layers)"
  ]
  ready: ->
    null
  onLayers: (layers) ->
    log('upd', layers)

    
Polymer
  is: "light9-paint"
  properties: {
    painting: { type: Object }
  }

  ready: () ->
    # couldn't make it work to bind to painting's notifyPath events
    @$.canvas.addEventListener('paintingChanged', @paintingChanged.bind(@))
    @$.solve.addEventListener('response', @onSolve.bind(@))
    
  paintingChanged: (ev) ->
    @painting = ev.detail
    @$.solve.body = JSON.stringify(@painting.getDoc())
    @$.solve.generateRequest()

  onSolve: (response) ->
    console.log(response)