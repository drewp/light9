model =
  songs: ko.observableArray([])

reconnectingWebSocket "ws://localhost:8070/songEffectsUpdates", (msg) ->
  console.log(msg.songs)
  model.songs(msg.songs)
  
ko.applyBindings(model)

  # there's a shorter unpack thing
  #writeBack = ko.computed ->
  #  console.log('sendback' ,{code: model.code()})
  