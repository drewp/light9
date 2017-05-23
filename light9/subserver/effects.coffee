class Model
  constructor: ->
    @classes = ko.observable([])
    
    @chases = ko.observable([])
    @moreExprs = [
      {label: "rainbow", expr: "hsv(t*1,1,1)"},
      {label: "pulserainbow", expr: "hsv(t*1,1,1)*nsin(t*2)"},
      {label: "stacrainbow", expr: "hsv(t*1,1,1)*(nsin(t*2)>.7)"},
      {label: "alternatergb", expr: "hsv(t*1,1,1, light='left')*nsin(t*3) + hsv(t*1,1,1,light='right')*(1-nsin(t*3))"},
      {label: "frontchase", expr: "chase(t, names=frontchase, ontime=.3, offset=-.11)"},
      {label: "bumpyhues", expr: "hsv(t*.5,.4,1)*notch(t*.01)"},
      ]

  subtermLink: (label, expr) =>
    "http://chase?"+$.param({
      subtermName: label
      subtermExpr: label + '_env(t) * ' + expr
      curve: label + '_env'
    })
  subtermExprs: (chase) =>
    [
      'chase(t, names=LABEL, ontime=0.5, offset=0.2)'.replace(/LABEL/g, chase.label)
    ]
  

model = new Model()

model.addToCurrentSong = (e) ->
  $.ajax({
    type: 'POST'
    url: '/effectEval/songEffects'
    data: {drop: e.uri}
  })

model.addMomentary = (e) ->
  $.ajax({
    type: 'POST'
    url: '/effectEval/songEffects'
    data: {drop: e.uri, event: 'start'}
  })

model.addMomentaryUp = (e) ->
  $.ajax({
    type: 'POST'
    url: '/effectEval/songEffects'
    data: {drop: e.uri, event: 'end'}
  })
  

reconnectingWebSocket "../effectsUpdates", (msg) ->
  model.chases(msg.chases) if msg.chases?
  model.classes(msg.classes) if msg.classes?

# this sort of works to stop clicks in <input> from following the
# submaster hyperlink, but it may make certain clicks act wrong
$(document).on('click', 'a', (ev) ->
  return false if ev.target.tagName == 'INPUT'
)

ko.applyBindings(model)