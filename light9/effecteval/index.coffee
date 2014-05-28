model =
  songs: ko.observableArray([])

model.dragover = (obj, event) ->
  event.preventDefault()
  event.originalEvent.dataTransfer.dropEffect = 'copy'

model.drop = (uri, event) ->
  event.preventDefault()
  dropped(uri, event.originalEvent.dataTransfer.getData('text/uri-list'))

dropped = (songTargetUri, dropUri) ->
  $.post('songEffects', {uri: songTargetUri, drop: dropUri})

reconnectingWebSocket "ws://localhost:8070/songEffectsUpdates", (msg) ->
  console.log(msg.songs)
  model.songs(msg.songs)
  
ko.applyBindings(model)

  # there's a shorter unpack thing
  #writeBack = ko.computed ->
  #  console.log('sendback' ,{code: model.code()})
  