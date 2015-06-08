class Model
  constructor: ->
    @subs = ko.observable([])
    @showLocal = ko.observable(false)

  snapshot: (sub) =>
    $.ajax({
      url: "snapshot"
      type: "POST"
      data: {about: sub.uri}
    })

model = new Model()

# this sort of works to stop clicks in <input> from following the
# submaster hyperlink, but it may make certain clicks act wrong
$(document).on('click', 'a', (ev) ->
  return false if ev.target.tagName == 'INPUT'
)

reconnectingWebSocket "live", (msg) ->
  model.subs(msg.subs) if msg.subs?


ko.applyBindings(model)