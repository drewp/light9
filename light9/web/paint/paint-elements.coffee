class Stroke
  constructor: (pos) ->
    @path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    @path.setAttributeNS(null, 'd', "M #{pos[0]} #{pos[1]}")
    @lastPos = pos

  appendElem: (parent) ->
    parent.appendChild(@path)
    
  move: (pos) ->
    if Math.hypot(pos[0] - @lastPos[0], pos[1] - @lastPos[1]) < 30
      return
    @path.attributes.d.value += " L #{pos[0]} #{pos[1]}"
    @lastPos = pos
  
Polymer
  is: "light9-paint"
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'onResize'
  properties: {
  }
  ready: ->
    @$.paint.addEventListener('mousedown', @onDown.bind(@))
    @$.paint.addEventListener('mousemove', @onMove.bind(@))
    @$.paint.addEventListener('mouseup', @onUp.bind(@))
    @$.paint.addEventListener('touchstart', @onDown.bind(@))
    @$.paint.addEventListener('touchmove', @onMove.bind(@))
    @$.paint.addEventListener('touchend', @onUp.bind(@))

  evPos: (ev) ->
    return (if ev.touches?.length? then [Math.round(ev.touches[0].clientX), Math.round(ev.touches[0].clientY)] else [ev.x, ev.y]) 

  onDown: (ev) ->
    # if it's on an existing one, do selection
    @stroke = new Stroke(@evPos(ev))
    @stroke.appendElem(@$.paint)
    @scopeSubtree(@$.paint)

  onMove: (ev) ->
    # ..or move selection
    return unless @stroke
    @stroke.move(@evPos(ev))

  onUp: (ev) ->
    @stroke = null

  onResize: (ev) ->
    @$.paint.attributes.viewBox.value = "0 0 #{ev.target.offsetWidth} 500"
    