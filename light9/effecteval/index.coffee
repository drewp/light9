model =
  songs: ko.observableArray([])

model.dragover = (obj, event) ->
  event.preventDefault()
  event.originalEvent.dataTransfer.dropEffect = 'copy'

model.drop = (uri, event) ->
  event.preventDefault()
  dropped(uri, event.originalEvent.dataTransfer.getData('text/uri-list'))

model.focusSong = (song) ->
  window.location.search = '?song=' + song.uri

dropped = (songTargetUri, dropUri) ->
  $.post('songEffects', {uri: songTargetUri, drop: dropUri})

deleteEffect = (uri) ->
  $.ajax
    type: 'DELETE'
    url: 'effect?' + $.param({uri: uri})
  console.log("del", uri)
  
reconnectingWebSocket "songEffectsUpdates", (msg) ->
  for s in msg.songs
    for e in s.effects
      do (e) ->
        e.deleteEffect = -> deleteEffect(e.uri)


  m = window.location.search.match(/song=(http[^&]+)/)
  if m
    model.songs((s for s in msg.songs when s.uri == m[1]))
  else
    model.songs(msg.songs)
  
ko.applyBindings(model)

  # there's a shorter unpack thing
  #writeBack = ko.computed ->
  #  console.log('sendback' ,{code: model.code()})
  