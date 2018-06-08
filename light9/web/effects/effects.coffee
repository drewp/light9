Polymer
  is: "light9-effects"
  properties: 
    graph: {type: Object}
    effectClasses: { type: Array }
  ready: ->
    @graph.runHandler(@getClasses.bind(@), 'getClasses')

  getClasses: ->
    U = (x) => @graph.Uri(x)
    @effectClasses = @graph.sortedUris(@graph.subjects(U('rdf:type'), U(':Effect')))

Polymer
  is: "light9-effect-class"
  properties: 
    graph: {type: Object}
    uri: {type: Object}
    
  onAdd: ->
    @$.songEffects.body = {drop: @uri.value}
    @$.songEffects.generateRequest()
    
  onMomentaryPress: ->
    @$.songEffects.body = {drop: @uri.value, event: 'start'}
    @lastPress = @$.songEffects.generateRequest()
    @lastPress.completes.then (request) =>
      @lastMomentaryNote = request.response.note
      
  onMomentaryRelease: ->
    return unless @lastMomentaryNote
    @$.songEffects.body = {drop: @uri.value, note: @lastMomentaryNote}
    @lastMomentaryNote = null
    @$.songEffects.generateRequest()
  