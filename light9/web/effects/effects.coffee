Polymer
  is: "light9-effects"
  properties: 
    graph: {type: Object}
    effectClasses: { type: Array }
  ready: ->
    @graph.runHandler(@getClasses.bind(@))

  getClasses: ->
    U = (x) => @graph.Uri(x)
    @effectClasses = _.sortBy(@graph.subjects(U('rdf:type'), U(':Effect')))

Polymer
  is: "light9-effect-class"
  properties: 
    graph: {type: Object}
    uri: {type: String}
    
  onAdd: ->
    @$.songEffects.body = {drop: @uri}
    @$.songEffects.generateRequest()
    
  onMomentaryPress: ->
    @$.songEffects.body = {drop: @uri, event: 'start'}
    @lastPress = @$.songEffects.generateRequest()
    @lastPress.completes.then (request) =>
      @lastMomentaryNote = request.response.note
      
  onMomentaryRelease: ->
    return unless @lastMomentaryNote
    @$.songEffects.body = {drop: @uri, note: @lastMomentaryNote}
    @lastMomentaryNote = null
    @$.songEffects.generateRequest()
  