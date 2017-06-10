RDFS = 'http://www.w3.org/2000/01/rdf-schema#'



window.setupDrop = (senseElem, highlightElem, coordinateOriginElem, onDrop) ->

  highlight = -> highlightElem.classList.add('dragging')
  unhighlight = -> highlightElem.classList.remove('dragging')
  
  senseElem.addEventListener 'drag', (event) =>
    
  senseElem.addEventListener 'dragstart', (event) =>
    
  senseElem.addEventListener 'dragend', (event) =>
    
  senseElem.addEventListener 'dragover', (event) =>
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    highlight()

  senseElem.addEventListener 'dragenter', (event) =>
    highlight()
    
  senseElem.addEventListener 'dragleave', (event) =>
    unhighlight()
   
  senseElem.addEventListener 'drop', (event) ->
    event.preventDefault()
    uri = event.dataTransfer.getData('text/uri-list')

    pos = if coordinateOriginElem?
        root = coordinateOriginElem.getBoundingClientRect()
        $V([event.pageX - root.left, event.pageY - root.top])
      else
        null

    onDrop(uri, pos)
    unhighlight()



Polymer
    is: "edit-choice",
    properties:
        graph: {type: Object, notify: true},
        uri: {type: String, notify: true},
        label: {type: String, notify: true}

    observers: [
      'gotGraph(graph, uri)'
      ]

    ready: ->
      @uri = null
      setupDrop @$.box, @$.box, null, (uri) =>
        @uri=uri
        @updateLabel()

    gotGraph: ->
      @graph.runHandler(@updateLabel.bind(@), "edit-choice #{@uri}")
        
    updateLabel: ->
      @label = try
          @graph.stringValue(@uri, RDFS + 'label')
        catch
          @uri

    unlink: ->
      @uri = null

