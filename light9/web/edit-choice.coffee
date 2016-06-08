RDFS = 'http://www.w3.org/2000/01/rdf-schema#'
Polymer
    is: "edit-choice",
    properties:
        graph: {type: Object, notify: true},
        uri: {type: String, notify: true},
        label: {type: String, notify: true}

    observers: [
      'gotGraph(graph, uri)'
      ]

    dragover: (event) ->
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
      @$.box.classList.add('over')

    dragleave: (event) ->
      @$.box.classList.remove('over')

    drop: (event) ->
      event.preventDefault()
      @uri = event.dataTransfer.getData('text/uri-list')
      @updateLabel()
      
    gotGraph: ->
      @graph.runHandler(@updateLabel.bind(@))
        
    updateLabel: ->
      @label = try
          @graph.stringValue(@uri, RDFS + 'label')
        catch
          @uri

