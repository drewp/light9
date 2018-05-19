log = console.log

coffeeElementSetup(class InlineAttrs extends Polymer.Element
  @is: "light9-timeline-note-inline-attrs"
  @getter_properties:
    graph: { type: Object, notify: true }
    song: { type: String, notify: true }
    config: { type: Object } # just for setup
    uri: { type: Object, notify: true }  # the Note
    effect: { type: Object, notify: true }
    effectStr: { type: String, notify: true }
    colorScale: { type: String, notify: true }
    noteLabel: { type: String, notify: true }
    selection: { type: Object, notify: true }
  @getter_observers: [
    'addHandler(graph, uri)'
    'onColorScale(graph, uri, colorScale)'
    '_onConfig(config)'
    '_effectToStr(effect)'
    '_effectToUri(effectStr, graph)'
    ]
  _effectToStr: (effect) ->
    @effectStr = @effect?.value
    log('now str is', @effectStr)
  _effectToUri: (effectStr, graph) ->
    if @effectStr
      @effect = @graph.Uri(@effectStr)
    else
      @effect = null
  _onConfig: ->
    @uri = @config.uri
    for side in ['top', 'left', 'width', 'height']
      @.style[side] = @config[side] + 'px'
    
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
    
  addHandler: ->
    return unless @uri
    @graph.runHandler(@update.bind(@), "update inline attrs #{@uri.value}")
    
  update: ->
    return unless @uri?
    console.time('attrs update')
    U = (x) => @graph.Uri(x)
    @effect = @graph.uriValue(@uri, U(':effectClass'))
    @noteLabel = @uri.value.replace(/.*\//, '')
    return
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
    deleteNote(@graph, @song, @uri, @selection)
)
