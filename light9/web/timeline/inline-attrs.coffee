log = console.log

coffeeElementSetup(class InlineAttrs extends Polymer.Element
  @is: "light9-timeline-note-inline-attrs"
  @getter_properties:
    graph: { type: Object, notify: true }
    song: { type: String, notify: true }
    config: { type: Object } # just for setup
    uri: { type: Object, notify: true }  # the Note
    effect: { type: Object, notify: true }
    colorScale: { type: String, notify: true }
    noteLabel: { type: String, notify: true }
    selection: { type: Object, notify: true }
  @getter_observers: [
    'addHandler(graph, uri)'
    'onColorScale(graph, uri, colorScale)'
    '_onConfig(config)'
    ]
  _onConfig: ->
    @uri = @config.uri
    for side in ['top', 'left', 'width', 'height']
      @.style[side] = @config[side] + 'px'

  displayed: ->
    @querySelector('light9-color-picker').displayed()
    
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
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: song}

    existingColorScaleSetting = null
    for setting in @graph.objects(note, U(':setting'))
      ea = @graph.uriValue(setting, U(':effectAttr'))
      if ea == attr
        existingColorScaleSetting = setting
        
    if existingColorScaleSetting
      @graph.patchObject(existingColorScaleSetting, U(':value'), value, song)
    else
      setting = @graph.nextNumberedResource(note + 'set')
      patch = {delQuads: [], addQuads: [
        quad(note, U(':setting'), setting)
        quad(setting, U(':effectAttr'), attr)
        quad(setting, U(':value'), value)
        ]}
      @graph.applyAndSendPatch(patch)
    
  addHandler: ->
    return
    @graph.runHandler(@update.bind(@), "update inline attrs #{@uri}")
    
  update: ->
    #console.time('attrs update')
    U = (x) => @graph.Uri(x)
    @effect = @graph.uriValue(@uri, U(':effectClass'))
    @noteLabel = @uri.replace(/.*\//, '')

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
    #console.timeEnd('attrs update')


  onDel: ->
    deleteNote(@graph, @song, @uri, @selection)
)
