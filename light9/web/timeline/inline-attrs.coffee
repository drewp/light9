log = console.log

coffeeElementSetup(class InlineAttrs extends Polymer.Element
  @is: "light9-timeline-note-inline-attrs"
  @getter_properties:
    graph: { type: Object, notify: true }
    project: { type: Object, notify: true }
    song: { type: String, notify: true }
    config: { type: Object } # just for setup
    uri: { type: Object, notify: true }  # the Note
    effectStr: { type: String, notify: true }
    colorScale: { type: String, notify: true }
    noteLabel: { type: String, notify: true }
    selection: { type: Object, notify: true }
  @getter_observers: [
    '_onConfig(config)'
    'addHandler(graph, uri)'
    'onColorScale(graph, uri, colorScale)'
    ]

  ready: ->
    super.ready()
    @$.effect.addEventListener 'edited', =>
      @graph.patchObject(@uri, @graph.Uri(':effectClass'), @graph.Uri(@effectStr), @graph.Uri(@song))
      
  _onConfig: ->
    @uri = @config.uri
    for side in ['top', 'left', 'width', 'height']
      @.style[side] = @config[side] + 'px'
    
  addHandler: ->
    return unless @uri
    @graph.runHandler(@update.bind(@), "update inline attrs #{@uri.value}")
    
  onColorScale: ->
    return
    U = (x) => @graph.Uri(x)
    if @colorScale == @colorScaleFromGraph
      return
    @editAttr(@song, @uri, U(':colorScale'), @graph.Literal(@colorScale))

  editAttr: (song, note, attr, value) ->
    U = (x) => @graph.Uri(x)
    if not song?
      log("can't edit inline attr yet, no song")
      return
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: U(song)}

    existingColorScaleSetting = null
    for setting in @graph.objects(note, U(':setting'))
      ea = @graph.uriValue(setting, U(':effectAttr'))
      if ea == attr
        existingColorScaleSetting = setting
        
    if existingColorScaleSetting
      @graph.patchObject(existingColorScaleSetting, U(':value'), value, U(song))
    else
      setting = @graph.nextNumberedResource(note.value + 'set')
      patch = {delQuads: [], addQuads: [
        quad(note, U(':setting'), setting)
        quad(setting, U(':effectAttr'), attr)
        quad(setting, U(':value'), value)
        ]}
      @graph.applyAndSendPatch(patch)
    
  update: ->
    console.time('attrs update')
    U = (x) => @graph.Uri(x)
    @effectStr = @graph.uriValue(@uri, U(':effectClass'))?.value
    @noteLabel = @uri.value.replace(/.*\//, '')
    existingColorScaleSetting = null
    for setting in @graph.objects(@uri, U(':setting'))
      ea = @graph.uriValue(setting, U(':effectAttr'))
      value = @graph.stringValue(setting, U(':value'))
      if ea == U(':colorScale')
        @colorScaleFromGraph = value
        @colorScale = value
        existingColorScaleSetting = setting
    if existingColorScaleSetting == null
      @colorScaleFromGraph = '#ffffff'
      @colorScale = '#ffffff'
    console.timeEnd('attrs update')

  onDel: ->
    @project.deleteNote(@graph.Uri(@song), @uri, @selection)
)
