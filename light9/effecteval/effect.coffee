model =
  code: ko.observable()
reconnectingWebSocket "ws://localhost:8070/effectData" + window.location.search, (msg) ->
  console.log('effectData ' + JSON.stringify(msg))
  # there's a shorter unpack thing
  writeBack = ko.computed ->
    console.log('sendback' ,{code: model.code()})
    
  model.code(msg.code)
  ko.applyBindings(model)
  