log = console.log

# Like element.set(path, newArray), but minimizes splices.
# Dotted paths don't work yet.
syncArray = (element, path, newArray, isElementEqual) ->
  pos = 0
  newPos = 0

  while newPos < newArray.length
    if pos < element[path].length
      if isElementEqual(element[path][pos], newArray[newPos])
        pos += 1
        newPos += 1
      else
        element.splice('devices', pos, 1)
    else
      element.push('devices', newArray[newPos])
      pos += 1
      newPos += 1

  if pos < element[path].length
    element.splice('devices', pos, element[path].length - pos)

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
    value: { type: Object, notify: true } # null, Uri, float, str
    choiceValue: { type: Object }
    
    immediateSlider: { notify: true, observer: 'onSlider' }
    sliderWriteValue: { type: Number }

    pickedChoice: { observer: 'onChange' }
    graphToControls: { type: Object }
  @getter_observers: [
    'onChange(value)'
    'onGraphToControls(graphToControls)'
    'onChoice(choiceValue)'
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
    if v == null
      @clear()
    else
      @value = v
    @sliderWriteValue = v if @deviceAttrRow.useSlider
    @choiceValue = (if v == null then v else v.value) if @deviceAttrRow.useChoice
    @enableChange = true

  onChoice: (value) ->
    return unless @graphToControls? and @enableChange
    if value?
      value = @graph.Uri(value)
    else
      value = null
    @graphToControls.controlChanged(@device, @deviceAttrRow.uri, value)
    
  onChange: (value) ->
    return unless @graphToControls? and @enableChange
    return if typeof value == "number" and isNaN(value) # let onChoice do it
    #log('change: control tells graph', @deviceAttrRow.uri.value, value)
    if value == undefined
      value = null
    @graphToControls.controlChanged(@device, @deviceAttrRow.uri, value)

  clear: ->
    @pickedChoice = null
    @sliderWriteValue = 0
    if @deviceAttrRow.useColor
      @value = '#000000'
    else if @deviceAttrRow.useChoice
      @value = @pickedChoice = null
    else
      @value = @immediateSlider = 0
)

coffeeElementSetup(class Light9LiveDeviceControl extends Polymer.Element
  @is: "light9-live-device-control"
  @getter_properties:
    graph: { type: Object, notify: true }
    uri: { type: String, notify: true }
    effect: { type: String }
    deviceClass: { type: String, notify: true } # the uri str
    deviceAttrs: { type: Array, notify: true }
    graphToControls: { type: Object }
    bgStyle: { type: String, computed: '_bgStyle(deviceClass)' }
    devClasses: { type: String, value: '' } # the css kind
  @getter_observers: [
    'onGraph(graph)'
    ]
  constructor: ->
    super()
    @selectedAttrs = new Set() # uri strings
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

  setDeviceSelected: (isSel) ->
    @devClasses = if isSel then 'selected' else ''

  setAttrSelected: (devAttr, isSel) ->
    if isSel
      @selectedAttrs.add(devAttr.value)
    else
      @selectedAttrs.delete(devAttr.value)
    @update()
    
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
      attrClasses: if @selectedAttrs.has(devAttr.value) then 'selected' else ''
      }
    if dataType.equals(U(':color'))
      daRow.useColor = true
    else if dataType.equals(U(':choice'))
      daRow.useChoice = true
      choiceUris = @graph.sortedUris(@graph.objects(devAttr, U(':choice')))
      daRow.choices = ({uri: x.value, label: @graph.labelOrTail(x)} for x in choiceUris)
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

  onClick: (ev) ->
    log('click', @uri)
    # select, etc

  onAttrClick: (ev) ->
    log('attr click', @uri, ev.model.dattr.uri)
    # select
)


class ActiveSettings
  constructor: (@graph) ->
    # The settings we're showing (or would like to but the widget
    # isn't registered yet):
    # dev+attr : {setting: Uri, onChangeFunc: f, jsValue: str_or_float}
    @settings = new Map()
    @keyForSetting = new Map() # setting uri str -> dev+attr

    # Registered graphValueChanged funcs, by dev+attr. Kept even when
    # settings are deleted.
    @onChanged = new Map()

  addSettingsRow: (device, deviceAttr, setting, value) ->
    key = device.value + " " + deviceAttr.value
    if @settings.has(key)
      throw new Error("repeated setting on "+key)
    if @keyForSetting.has(setting.value)
      throw new Error("repeated keyForSetting on "+setting.value)
    @settings.set(key, {
      setting: setting,
      onChangeFunc: @onChanged[key],
      jsValue: value
    })
    @keyForSetting.set(setting.value, key)
    if @onChanged[key]?
      @onChanged[key](value)

  has: (setting) ->
    @keyForSetting.has(setting.value)

  setValue: (setting, value) ->
    row = @settings.get(@keyForSetting.get(setting.value))
    row.jsValue = value
    row.onChangeFunc(value) if row.onChangeFunc?

  registerWidget: (device, deviceAttr, graphValueChanged) ->
    key = device.value + " " + deviceAttr.value
    @onChanged[key] = graphValueChanged
    
    if @settings.has(key)
      row = @settings.get(key)
      row.onChangeFunc = graphValueChanged
      row.onChangeFunc(row.jsValue)

  effectSettingLookup: (device, attr) ->
    key = device.value + " " + attr.value
    if @settings.has(key)
      return @settings.get(key).setting

    return null

  deleteSetting: (setting) ->
    log('deleteSetting ' + setting.value)
    key = @keyForSetting.get(setting.value)
    row = @settings.get(key)
    if row? and not row.setting.equals(setting)
      throw new Error('corrupt row for ' + setting.value)
    row.onChangeFunc(null) if row?.onChangeFunc?
    @settings.delete(key)
    @keyForSetting.delete(setting)

  clear: ->
    new Map(@settings).forEach (row, key) ->
      row.onChangeFunc(null) if row.onChangeFunc?
    @settings.clear()
    @keyForSetting.clear()

  forAll: (cb) ->
    all = Array.from(@keyForSetting.keys())
    for s in all
      cb(@graph.Uri(s))

  allSettingsStr: ->
    @keyForSetting.keys()

class GraphToControls
  # More efficient bridge between liveControl widgets and graph edits,
  # as opposed to letting each widget scan the graph and push lots of
  # tiny patches to it.
  constructor: (@graph) ->
    @activeSettings = new ActiveSettings(@graph)
    @effect = null

  ctxForEffect: (effect) ->
    @graph.Uri(effect.value.replace(
      "light9.bigasterisk.com/effect",
      "light9.bigasterisk.com/show/dance2019/effect"))
      
  setEffect: (effect) ->
    @clearSettings()
    @effect = effect
    @ctx = @ctxForEffect(@effect)
    # are these going to pile up? consider @graph.triggerHandler('GTC sync')
    @graph.runHandler(@syncFromGraph.bind(@), 'GraphToControls sync')

  newEffect: ->
    # wrong- this should be our editor's scratch effect, promoted to a
    # real one when you name it.
    U = (x) => @graph.Uri(x)
    effect = @graph.nextNumberedResource(U('http://light9.bigasterisk.com/effect/effect'))
    ctx = @ctxForEffect(effect)
    quad = (s, p, o) => @graph.Quad(s, p, o, ctx)

    addQuads = [
      quad(effect, U('rdf:type'), U(':Effect'))
      quad(effect, U('rdfs:label'), @graph.Literal(effect.value.replace(/.*\//, "")))
      quad(effect, U(':publishAttr'), U(':strength'))
    ]
    patch = {addQuads: addQuads, delQuads: []}
    log('init new effect', patch)
    @graph.applyAndSendPatch(patch)
    return effect

  syncFromGraph: ->
    U = (x) => @graph.Uri(x)
    return if not @effect
    
    toClear = new Set(@activeSettings.allSettingsStr())
    
    for setting in @graph.objects(@effect, U(':setting'))
      dev = @graph.uriValue(setting, U(':device'))
      devAttr = @graph.uriValue(setting, U(':deviceAttr'))

      pred = valuePred(@graph, devAttr)
      try
        value = @graph.uriValue(setting, pred)
        if not value.id.match(/^http/)
          throw new Error("not uri")
      catch
        try
          value = @graph.floatValue(setting, pred)
        catch
          value = @graph.stringValue(setting, pred)
      log('change: graph contains', devAttr, value)

      if @activeSettings.has(setting)
        @activeSettings.setValue(setting, value)
        toClear.delete(setting.value)
      else
        @activeSettings.addSettingsRow(dev, devAttr, setting, value)
          
    for settingStr in Array.from(toClear)
      @activeSettings.deleteSetting(U(settingStr))

  clearSettings: ->
    @activeSettings.clear()

  register: (device, deviceAttr, graphValueChanged) ->
    @activeSettings.registerWidget(device, deviceAttr, graphValueChanged)

  shouldBeStored: (deviceAttr, value) ->
    # this is a bug for zoom=0, since collector will default it to
    # stick at the last setting if we don't explicitly send the
    # 0. rx/ry similar though not the exact same deal because of
    # their remap.
    return value? and value != 0 and value != '#000000'

  emptyEffect: ->
    @activeSettings.forAll(@_removeEffectSetting.bind(@))

  controlChanged: (device, deviceAttr, value) ->
    # value is float or #color or (Uri or null)
    if (value == undefined or (typeof value == "number" and isNaN(value)) or (typeof value == "object" and value != null and not value.id))
      throw new Error("controlChanged sent bad value " + value)
    effectSetting = @activeSettings.effectSettingLookup(device, deviceAttr)

    # sometimes this misses an existing setting, which leads to a mess
    
    if @shouldBeStored(deviceAttr, value)
      if not effectSetting?
        @_addEffectSetting(device, deviceAttr, value)
      else
        @_patchExistingEffectSetting(effectSetting, deviceAttr, value)
    else
      @_removeEffectSetting(effectSetting)

  _nodeForValue: (value) ->
    if value.id?
      return value
    return @graph.prettyLiteral(value)

  _addEffectSetting: (device, deviceAttr, value) ->
    log('change: _addEffectSetting', deviceAttr.value, value)
    U = (x) => @graph.Uri(x)
    quad = (s, p, o) => @graph.Quad(s, p, o, @ctx)
    effectSetting = @graph.nextNumberedResource(@effect.value + '_set')
    @activeSettings.addSettingsRow(device, deviceAttr, effectSetting, value)
    addQuads = [
      quad(@effect, U(':setting'), effectSetting),
      quad(effectSetting, U(':device'),  device),
      quad(effectSetting, U(':deviceAttr'), deviceAttr),
      quad(effectSetting, valuePred(@graph, deviceAttr), @_nodeForValue(value))
    ]
    patch = {addQuads: addQuads, delQuads: []}
    log('save', patch)
    @graph.applyAndSendPatch(patch)

  _patchExistingEffectSetting: (effectSetting, deviceAttr, value) ->
    log('change: patch existing', effectSetting.value)
    @activeSettings.setValue(effectSetting, value)
    @graph.patchObject(effectSetting, valuePred(@graph, deviceAttr), @_nodeForValue(value), @ctx)

  _removeEffectSetting: (effectSetting) ->
    U = (x) => @graph.Uri(x)
    quad = (s, p, o) => @graph.Quad(s, p, o, @ctx)
    if effectSetting?
      log('change: _removeEffectSetting', effectSetting.value)
      toDel = [quad(@effect, U(':setting'), effectSetting, @ctx)]
      for q in @graph.graph.getQuads(effectSetting)
        toDel.push(q)
      @graph.applyAndSendPatch({delQuads: toDel, addQuads: []})
      @activeSettings.deleteSetting(effectSetting)
    
    
coffeeElementSetup(class Light9LiveControls extends Polymer.Element
  @is: "light9-live-controls"
  @getter_properties:
    graph: { type: Object, notify: true }
    devices: { type: Array, notify: true, value: [] }
    # string uri of the effect being edited, or null. This is the
    # master value; GraphToControls follows.
    effectChoice: { type: String, notify: true, value: null }
    graphToControls: { type: Object }
  @getter_observers: [
    'onGraph(graph)'
    'onEffectChoice(effectChoice)'
    ]

  constructor: ->
    super()
    @graphToControls = null

  ready: ->
    super.ready()
    @currentSettings = {}

  onGraph: ->
    @graphToControls = new GraphToControls(@graph)
    @graph.runHandler(@update.bind(@), 'Light9LiveControls update')

    # need graph to be loaded, so we don't make double settings? not sure.
    setTimeout(@setFromUrl.bind(@), 1)

  setFromUrl: ->
    effect = new URL(window.location.href).searchParams.get('effect')
    if effect?
      @effectChoice = effect

  newEffect: ->
    @effectChoice = @graphToControls.newEffect().value
      
  onEffectChoice: ->
    U = (x) => @graph.Uri(x)
    if not @effectChoice?
      # unlink
      @graphToControls.setEffect(null) if @graphToControls?
    else
      log('load', @effectChoice)
      @graphToControls.setEffect(@graph.Uri(@effectChoice)) if @graphToControls?
 
  clearAll: ->
    # clears the effect!
    @graphToControls.emptyEffect()
    
  update: ->
    U = (x) => @graph.Uri(x)

    newDevs = []
    for dc in @graph.sortedUris(@graph.subjects(U('rdf:type'), U(':DeviceClass')))
      for dev in @graph.sortedUris(@graph.subjects(U('rdf:type'), dc))
        newDevs.push({uri: dev})

    syncArray(@, 'devices', newDevs, (a, b) -> a.uri.value == b.uri.value)

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