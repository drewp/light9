class Painting
  constructor: (@svg) ->
    @strokes = []

  setSize: (@size) ->

  startStroke: (pos, color) ->
    stroke = new Stroke(pos, color, @size)
    stroke.appendElem(@svg)
    @strokes.push(stroke)
    return stroke

  hover: (pos) ->
    @clear()
    s = @startStroke(pos, '#ffffff', @size)
    r = .02
    steps = 5
    for ang in [0..steps]
      ang = 6.28 * ang / steps
      s.move([pos[0] + r * Math.sin(ang), pos[1] + 1.5 * r * Math.cos(ang)])

  getDoc: ->
    {strokes: @strokes}

  clear: ->
    s.removeElem() for s in @strokes
    @strokes = []

class Stroke
  constructor: (pos, @color, @size) ->
    @path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    @path.setAttributeNS(null, 'd', "M #{pos[0]*@size[0]} #{pos[1]*@size[1]}")
    @pts = [pos]
    @lastPos = pos

  appendElem: (parent) ->
    parent.appendChild(@path)

  removeElem: ->
    @path.remove()
    
  move: (pos) ->
    if Math.hypot(pos[0] - @lastPos[0], pos[1] - @lastPos[1]) < .02
      return
    @path.attributes.d.value += " L #{pos[0]*@size[0]} #{pos[1]*@size[1]}"
    @pts.push(pos)
    @lastPos = pos

  finish: () ->

Polymer
  is: "light9-paint-canvas"
  behaviors: [ Polymer.IronResizableBehavior ]
  listeners: 'iron-resize': 'onResize'
  properties: {
    bg: { type: String },
    tool: { type: String, value: 'hover' },
    painting: { type: Object } # output
  }
  ready: ->
    @painting = new Painting(@$.paint)
    @onResize()
    @$.paint.addEventListener('mousedown', @onDown.bind(@))
    @$.paint.addEventListener('mousemove', @onMove.bind(@))
    @$.paint.addEventListener('mouseup', @onUp.bind(@))
    @$.paint.addEventListener('touchstart', @onDown.bind(@))
    @$.paint.addEventListener('touchmove', @onMove.bind(@))
    @$.paint.addEventListener('touchend', @onUp.bind(@))

    @hover = _.throttle((ev) =>
          @painting.hover(@evPos(ev))
          @scopeSubtree(@$.paint)
          @fire('paintingChanged', @painting)
        , 100)

  evPos: (ev) ->
    px = (if ev.touches?.length? then [Math.round(ev.touches[0].clientX),
                                       Math.round(ev.touches[0].clientY)] else [ev.x, ev.y])
    return [px[0] / @size[0], px[1] / @size[1]]

  onClear: () ->
    @painting.clear()
    @fire('paintingChanged', @painting)
    
  onDown: (ev) ->
    switch @tool
      when "hover"
        @onMove(ev)
      when "paint"
        # if it's on an existing one, do selection
        @currentStroke = @painting.startStroke(@evPos(ev), '#aaaaaa')
    @scopeSubtree(@$.paint)

  onMove: (ev) ->
    switch @tool
      when "hover"
        @hover(ev)

      when "paint"
        # ..or move selection
        return unless @currentStroke
        @currentStroke.move(@evPos(ev))

  onUp: (ev) ->
    return unless @currentStroke
    @currentStroke.finish()
    @currentStroke = null
    
    @notifyPath('painting.strokes.length') # not working
    @fire('paintingChanged', @painting)

  onResize: (ev) ->
    @size = [@$.parent.offsetWidth, @$.parent.offsetHeight]
    @$.paint.attributes.viewBox.value = "0 0 #{@size[0]} #{@size[1]}"
    @painting.setSize(@size)


Polymer
  is: "light9-simulation"
  properties: {
    graph: { type: Object }
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
  is: "light9-device-settings",
  properties: {
    graph: { type: Object }
    subj: {type: String, notify: true},
    label: {type: String, notify: true},
    attrs: {type: Array, notify: true},
  },
  observers: [
    'onSubj(graph, subj)'
  ]
  ready: ->
    @label = "aura2"
    @attrs = [
        {attr: 'rx', val: .03},
        {attr: 'color', val: '#ffe897'},
    ]
  onSubj: (graph, @subj) ->
    graph.runHandler(@loadAttrs.bind(@), "loadAttrs #{@subj}")
  loadAttrs: ->
    U = (x) => @graph.Uri(x)
    @attrs = []
    for s in @graph.objects(U(@subj), U(':setting'))
      attr = @graph.uriValue(s, U(':deviceAttr'))
      attrLabel = @graph.stringValue(attr, U('rdfs:label'))
      @push('attrs', {attr: attrLabel, val: @graph.floatValue(s, U(':value'))})
    

    
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
