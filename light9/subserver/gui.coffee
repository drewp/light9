class Model
  constructor: ->
    @subs = ko.observable([])
    @showLocal = ko.observable(false)

model = new Model()

# this sort of works to stop clicks in <input> from following the
# submaster hyperlink, but it may make certain clicks act wrong
$('a').live('click', (ev) ->
  return false if ev.target.tagName == 'INPUT'
)

reconnectingWebSocket "ws://localhost:8052/live", (msg) ->
  model.subs(msg.subs) if msg.subs?


ko.applyBindings(model)