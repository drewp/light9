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
    return unless @uri? and @colorScale? and @colorScaleFromGraph?
    U = (x) => @graph.Uri(x)
    if @colorScale == @colorScaleFromGraph
      return
    @editAttr(@uri, U(':colorScale'), @graph.Literal(@colorScale))

  editAttr: (note, attr, value) ->
    U = (x) => @graph.Uri(x)
    if not @song?
      log("inline: can't edit inline attr yet, no song")
      return

    existingColorScaleSetting = null
    for setting in @graph.objects(note, U(':setting'))
      ea = @graph.uriValue(setting, U(':effectAttr'))
      if ea.equals(attr)
        existingColorScaleSetting = setting
        
    if existingColorScaleSetting
      log('inline: update setting', existingColorScaleSetting.value)
      @graph.patchObject(existingColorScaleSetting, U(':value'), value, U(@song))
    else
      log('inline: new setting')
      setting = @graph.nextNumberedResource(note.value + 'set')
      patch = {delQuads: [], addQuads: [
        @graph.Quad(note, U(':setting'), setting, U(@song))
        @graph.Quad(setting, U(':effectAttr'), attr, U(@song))
        @graph.Quad(setting, U(':value'), value, U(@song))
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
      if ea.equals(U(':colorScale'))
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
