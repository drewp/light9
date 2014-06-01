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

deleteEffect = (uri) ->
  $.ajax
    type: 'DELETE'
    url: 'effect?' + $.param({uri: uri})
  console.log("del", uri)
  
reconnectingWebSocket "ws://localhost:8070/songEffectsUpdates", (msg) ->
  for s in msg.songs
    for e in s.effects
      do (e) ->
        e.deleteEffect = -> deleteEffect(e.uri)

  model.songs(msg.songs)
  
ko.applyBindings(model)

  # there's a shorter unpack thing
  #writeBack = ko.computed ->
  #  console.log('sendback' ,{code: model.code()})
  