class Model
  constructor: ->
    @chases = ko.observable([])

  subtermLink: (label, expr) =>
    "http://chase?"+$.param({
      subtermName: label
      subtermExpr: expr
      curve: label
    })
  subtermExprs: (chase) =>
    [
      'LABEL(t) * chase(t, names=LABEL, ontime=0.5, offset=0.2)'.replace(/LABEL/g, chase.label)
    ]


model = new Model()

# this sort of works to stop clicks in <input> from following the
# submaster hyperlink, but it may make certain clicks act wrong
$('a').live('click', (ev) ->
  return false if ev.target.tagName == 'INPUT'
)

reconnectingWebSocket "ws://localhost:8052/live", (msg) ->
  model.chases(msg.chases) if msg.chases?


ko.applyBindings(model)