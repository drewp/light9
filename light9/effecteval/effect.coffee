qs = new QueryString()
model =
  toSave: 
    uri: ko.observable(qs.value('uri'))
    codeLines: ko.observableArray([])
  
socket = reconnectingWebSocket "ws://localhost:8070/effectUpdates" + window.location.search, (msg) ->
  console.log('effectData ' + JSON.stringify(msg))
  model.toSave.codeLines(msg.codeLines.map((x) -> {text: ko.observable(x)})) if msg.codeLines?

model.saveCode = ->
  $.ajax
    type: 'PUT'
    url: 'code'
    data: ko.toJS(model.toSave)

writeBack = ko.computed(model.saveCode)
  
ko.applyBindings(model)
  