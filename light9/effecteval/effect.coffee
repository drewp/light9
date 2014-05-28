qs = new QueryString()
model =
  uri: ko.observable(qs.value('uri'))
  code: ko.observable()
  
reconnectingWebSocket "ws://localhost:8070/effectUpdates" + window.location.search, (msg) ->
  console.log('effectData ' + JSON.stringify(msg))
  # there's a shorter unpack thing
    
  model.code(msg.code)
  
writeBack = ko.computed ->
  console.log('sendback' ,{code: model.code()})
  
ko.applyBindings(model)
  