
class Model
  constructor: ->
    @subs = ko.observable([])

model = new Model()

reconnectingWebSocket "ws://localhost:8052/live", (msg) ->
  model.subs(msg.subs) if msg.subs?


ko.applyBindings(model)