class Painting
  constructor: ->
    @strokes = []

  addStroke: (pts, color) ->
    @strokes.push({pts: pts, color: color})

  getDoc: ->
    {strokes: @strokes}

class Stroke
  constructor: (pos, @color) ->
    @path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    @path.setAttributeNS(null, 'd', "M #{pos[0]} #{pos[1]}")
    @pts = [pos]
    @lastPos = pos

  appendElem: (parent) ->
    parent.appendChild(@path)
    
  move: (pos) ->
    if Math.hypot(pos[0] - @lastPos[0], pos[1] - @lastPos[1]) < 30
      return
    @path.attributes.d.value += " L #{pos[0]} #{pos[1]}"
    @pts.push(pos)
    @lastPos = pos
  
Polymer
  is: "light9-paint"
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'onResize'
  properties: {
    layers: { type: Object }
  }
  ready: ->
    @painting = new Painting()
    @$.paint.addEventListener('mousedown', @onDown.bind(@))
    @$.paint.addEventListener('mousemove', @onMove.bind(@))
    @$.paint.addEventListener('mouseup', @onUp.bind(@))
    @$.paint.addEventListener('touchstart', @onDown.bind(@))
    @$.paint.addEventListener('touchmove', @onMove.bind(@))
    @$.paint.addEventListener('touchend', @onUp.bind(@))

  evPos: (ev) ->
    return (if ev.touches?.length? then [Math.round(ev.touches[0].clientX),
                                         Math.round(ev.touches[0].clientY)] else [ev.x, ev.y]) 

  onDown: (ev) ->
    # if it's on an existing one, do selection
    @stroke = new Stroke(@evPos(ev), '#aaaaaa')
    @stroke.appendElem(@$.paint)
    @scopeSubtree(@$.paint)

  onMove: (ev) ->
    # ..or move selection
    return unless @stroke
    @stroke.move(@evPos(ev))

  onUp: (ev) ->
    @painting.addStroke(@stroke.pts, @stroke.color)
    @$.solve.body = JSON.stringify(@painting.getDoc())
    @$.solve.generateRequest()
    @stroke = null

  onResize: (ev) ->
    @$.paint.attributes.viewBox.value = "0 0 #{ev.target.offsetWidth} 500"


Polymer
  is: "light9-simulation"
  properties: {
    layers: { type: Object }
  }
  listeners: [
    "onLayers(layers)"
  ]
  ready: ->
    null
  onLayers: (layers) ->
    log('upd', layers)