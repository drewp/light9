log = console.log

valuePred = (graph, attr) ->
  U = (x) -> graph.Uri(x)
  scaledAttributeTypes = [U(':color'), U(':brightness'), U(':uv')]
  if _.some(scaledAttributeTypes,
            (x) -> attr.equals(x)) then U(':scaledValue') else U(':value')

coffeeElementSetup(class Light9LiveControl extends Polymer.Element
  @is: 'light9-live-control'
  @getter_properties:
    graph: { type: Object, notify: true }
    device: { type: Object }
    deviceAttrRow: { type: Object } # object returned from attrRow, below
    value: { type: Object, notify: true }
    
    immediateSlider: { notify: true, observer: 'onSlider' }
    sliderWriteValue: { type: Number }

    pickedChoice: { observer: 'onChange' }
    graphToControls: { type: Object }
  @getter_observers: [
    'onChange(value)'
    'onGraphToControls(graphToControls)'
    ]
  constructor: ->
    super()
    @enableChange = false # until 1st graph read
  onSlider: -> @value = @immediateSlider
  goBlack: -> @value = "#000000"
  onGraphToControls: (gtc) ->
    gtc.register(@device, @deviceAttrRow.uri, @graphValueChanged.bind(@))
    @enableChange = true

  graphValueChanged: (v) ->
    log('change: control gets', v)
    @enableChange = false
    @value = v
    @sliderWriteValue = v if @deviceAttrRow.useSlider
    @enableChange = true
  onChange: (value) ->
    return unless @graphToControls? and @enableChange
    log('change: control tells graph', @deviceAttrRow.uri.value, value)
    @graphToControls.controlChanged(@device, @deviceAttrRow.uri, value)

  clear: ->
    @pickedChoice = null
    @sliderWriteValue = 0
    if @deviceAttrRow.useColor
      @value = '#000000'
    else
      @value = @immediateSlider = 0
)

coffeeElementSetup(class Light9LiveDeviceControl extends Polymer.Element
  @is: "light9-live-device-control"
  @getter_properties:
    graph: { type: Object, notify: true }
    uri: { type: String, notify: true }
    effect: { type: String }
    deviceClass: { type: String, notify: true }
    deviceAttrs: { type: Array, notify: true }
    graphToControls: { type: Object }
    bgStyle: { type: String, computed: '_bgStyle(deviceClass)' }
  @getter_observers: [
    'onGraph(graph)'
    ]
  _bgStyle: (deviceClass) ->
    hash = 0
    deviceClass = deviceClass.value
    for i in [(deviceClass.length-10)...deviceClass.length]
      hash += deviceClass.charCodeAt(i)
    hue = (hash * 8) % 360
    accent = "hsl(#{hue}, 49%, 22%)"
    "background: linear-gradient(to right, rgba(31,31,31,0) 50%, #{accent} 100%);"
    
  onGraph: ->
    @graph.runHandler(@update.bind(@), "#{@uri.value} update")
    
  update: (patch) ->
    U = (x) => @graph.Uri(x)
    return if patch? and not SyncedGraph.patchContainsPreds(
      patch, [U('rdf:type'), U(':deviceAttr'), U(':dataType'), U(':choice')])
    @deviceClass = @graph.uriValue(@uri, U('rdf:type'))
    @deviceAttrs = []
    for da in _.unique(@graph.sortedUris(@graph.objects(@deviceClass, U(':deviceAttr'))))
      @push('deviceAttrs', @attrRow(da))

  attrRow: (devAttr) ->
    U = (x) => @graph.Uri(x)
    dataType = @graph.uriValue(devAttr, U(':dataType'))
    daRow = {
      uri: devAttr
      dataType: dataType
      showColorPicker: dataType.equals(U(':color'))
      }
    if dataType.equals(U(':color'))
      daRow.useColor = true
    else if dataType.equals(U(':choice'))
      daRow.useChoice = true
      choiceUris = @graph.sortedUris(@graph.objects(devAttr, U(':choice')))
      daRow.choices = ({uri: x, label: @graph.labelOrTail(x)} for x in choiceUris)
      daRow.choiceSize = Math.min(choiceUris.length + 1, 10)
    else
      daRow.useSlider = true
      daRow.max = 1
      if dataType.equals(U(':angle'))
        # varies
        daRow.max = 1
    return daRow
      
  clear: ->
    for lc in @shadowRoot.querySelectorAll("light9-live-control")
      lc.clear()
    
)

class GraphToControls
  # More efficient bridge between liveControl widgets and graph edits,
  # as opposed to letting each widget scan the graph and push lots of
  # tiny patches to it.
  constructor: (@graph) ->
    @currentSettings = {} # {dev: {attr: value}}
    @onChanged = {}
    @effect = @graph.Uri('http://light9.bigasterisk.com/effect/pool_r')
    @ctx = @graph.Uri('http://light9.bigasterisk.com/show/dance2017/effect/pool_r')
    @graph.runHandler(@syncFromGraph.bind(@), 'GraphToControls sync')

  syncFromGraph: ->
    U = (x) => @graph.Uri(x)
    @currentSettings = {}
    return if not @effect
    for s in @graph.objects(@effect, U(':setting'))
      dev = @graph.uriValue(s, U(':device'))
      devAttr = @graph.uriValue(s, U(':deviceAttr'))

      pred = valuePred(@graph, devAttr)
      try
        value = @graph.floatValue(s, pred)
      catch
        value = @graph.stringValue(s, pred)
      log('change: graph contains', devAttr, value)

      oc = @onChanged[dev.value + " " + devAttr.value]
      if oc?
        log('change: gtc tells control')
        oc(value)

      # currentSettings is no longer what we need- the point is to
      # optimize effectSettingLookup by knowing the :setting nodes for
      # every dev+devAttr
                  
      # this is a bug for zoom=0, since collector will default it to
      # stick at the last setting if we don't explicitly send the
      # 0. rx/ry similar though not the exact same deal because of
      # their remap.
      if value == 0 or value == '#000000' or value == null or value == undefined
        delete @currentSettings[dev.value][devAttr.value] if @currentSettings[dev.value]?
      else
        @currentSettings[dev.value] = {} unless @currentSettings[dev.value]?
        @currentSettings[dev.value][devAttr.value] = value

  effectSettingLookup: (device, attr) ->
    U = (x) => @graph.Uri(x)
    for s in @graph.objects(@effect, U(':setting'))
      if @graph.uriValue(s, U(':device')).equals(device) and @graph.uriValue(s, U(':deviceAttr')).equals(attr)
        return s
    return null

    # faster one:
    d = @currentSettings[device.value]
    if d?
      da = d[attr.value]
      # ...
    return null
      
  preview: ->
    JSON.stringify(@currentSettings)

  register: (device, deviceAttr, graphValueChanged) ->
    log('change: registering', device, deviceAttr)
    @onChanged[device.value + " " + deviceAttr.value] = graphValueChanged
    da = @currentSettings[device.value]
    if da?
      v = da[deviceAttr.value]
      if v?
        log('change: gtc tells change at reg time', v)
        graphValueChanged(v)
    # no unregister yet

  shouldBeStored: (deviceAttr, value) ->
    # this is a bug for zoom=0, since collector will default it to
    # stick at the last setting if we don't explicitly send the
    # 0. rx/ry similar though not the exact same deal because of
    # their remap.
    return value != 0 and value != '#000000'

  controlChanged: (device, deviceAttr, value) ->
    effectSetting = @effectSettingLookup(device, deviceAttr)
    if @shouldBeStored(deviceAttr, value)
      if not effectSetting?
        @_addEffectSetting(device, deviceAttr, value)
      else
        @_patchExistingEffectSetting(effectSetting, deviceAttr, value)
    else
      @_removeEffectSetting(effectSetting)

  _addEffectSetting: (device, deviceAttr, value) ->
    U = (x) => @graph.Uri(x)
    quad = (s, p, o) => @graph.Quad(s, p, o, @ctx)
    effectSetting = @graph.nextNumberedResource(@effect.value + '_set')
    addQuads = [
      quad(@effect, U(':setting'), effectSetting),
      quad(effectSetting, U(':device'),  device),
      quad(effectSetting, U(':deviceAttr'), deviceAttr),
      quad(effectSetting, valuePred(@graph, deviceAttr), @graph.prettyLiteral(value))
    ]
    patch = {addQuads: addQuads, delQuads: []}
    log('save', patch)
    @graph.applyAndSendPatch(patch)

  _patchExistingEffectSetting: (effectSetting, deviceAttr, value) ->
    log('patch existing', effectSetting.value)
    @graph.patchObject(effectSetting, valuePred(@graph, deviceAttr), @graph.prettyLiteral(value), @ctx)

  _removeEffectSetting: (effectSetting) ->
    U = (x) => @graph.Uri(x)
    if effectSetting?
      toDel = [quad(@effect, U(':setting'), effectSetting, @ctx)]
      for q in @graph.graph.getQuads(effectSetting)
        toDel.push(q)
      @graph.applyAndSendPatch({delQuads: toDel, addQuads: []})
    
    
coffeeElementSetup(class Light9LiveControls extends Polymer.Element
  @is: "light9-live-controls"
  @getter_properties:
    graph: { type: Object, notify: true }
    devices: { type: Array, notify: true }
    effectPreview: { type: String, notify: true }
    newEffectName: { type: String, notify: true }
    effect: { type: String, notify: true } # the one being edited, if any
    graphToControls: { type: Object }
  @getter_observers: [
    'onGraph(graph)'
    'onEffect(effect)'
    ]

  constructor: ->
    super()
    @graphToControls = null
  ready: ->
    super.ready()
    @currentSettings = {}
    @effectPreview = JSON.stringify({})

  onGraph: ->
    @graphToControls = new GraphToControls(@graph)
    @effect = @graphToControls.effect.value
    log('set my @graphtocontrols')
    @graph.runHandler(@update.bind(@), 'Light9LiveControls update')

  effectSettingLookup: (device, attr) ->
    if @graphToControls == null
      throw new Error('not ready')
    # optimization for getting the :setting node
    return @graphToControls.effectSettingLookup(device, attr)
      
  onEffect: ->
    U = (x) => @graph.Uri(x)
    return unless @effect
    log('load', @effect)
    for s in @graph.objects(@effect, U(':setting'))
      dev = @graph.uriValue(s, U(':device'))
      devAttr = @graph.uriValue(s, U(':deviceAttr'))

      pred = valuePred(@graph, devAttr)
      try
        value = @graph.floatValue(s, pred)
      catch
        value = @graph.stringValue(s, pred)
      log('got', devAttr, value)
      window.gather([[dev, devAttr, value]])
      # there's nothing here to set the widgets to these values.
            
  saveNewEffect: ->
    uriName = @newEffectName.replace(/[^a-zA-Z0-9_]/g, '')
    return if not uriName.length

    U = (x) => @graph.Uri(x)

    @effect = U(U(":effect").value + "/#{uriName}")
    ctx = U("http://light9.bigasterisk.com/show/dance2017/effect/#{uriName}")
    quad = (s, p, o) => @graph.Quad(s, p, o, ctx)

    addQuads = [
      quad(@effect, U('rdf:type'), U(':Effect'))
      quad(@effect, U('rdfs:label'), @graph.Literal(@newEffectName))
      quad(@effect, U(':publishAttr'), U(':strength'))
      ]
    settings = @graph.nextNumberedResources(@effect.value + '_set', @currentSettingsList().length)
    for row in @currentSettingsList()
      setting = settings.shift()
      addQuads.push(quad(@effect, U(':setting'), setting))
      addQuads.push(quad(setting, U(':device'), row[0]))
      addQuads.push(quad(setting, U(':deviceAttr'), row[1]))
   
      addQuads.push(quad(setting, valuePred(@graph, row[1]), value))
      
    patch = {addQuads: addQuads, delQuads: []}
    log('save', patch)
    @graph.applyAndSendPatch(patch)
    @newEffectName = ''
    
  clearAll: ->
    for dc in @shadowRoot.querySelectorAll("light9-live-device-control")
      dc.clear()
    
  update: ->
    U = (x) => @graph.Uri(x)

    @set('devices', [])
    for dc in @graph.sortedUris(@graph.subjects(U('rdf:type'), U(':DeviceClass')))
      for dev in @graph.sortedUris(@graph.subjects(U('rdf:type'), dc))
        @push('devices', {uri: dev})

    return

    # Tried css columns- big slowdown from relayout as I'm scrolling.
    # Tried isotope- seems to only scroll to the right.
    # Tried columnize- fails in jquery maybe from weird elements.
    
    # not sure how to get this run after the children are created
    setTimeout((() -> $('#deviceControls').isotope({
      # fitColumns would be nice, but it doesn't scroll vertically
      layoutMode: 'masonry',
      containerStyle: null
      })), 2000)
)