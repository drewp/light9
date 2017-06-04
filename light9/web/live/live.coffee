log = console.log

Polymer
  is: 'light9-live-control'
  properties:
    device: { type: String }
    deviceAttr: { type: Object }
    max: { type: Number, value: 1 }
    value: { type: Object, notify: true }
    
    immediateSlider: { notify: true, observer: 'onSlider' }
    pickedColor: { observer: 'onPickedColor' }
    pickedChoice: { observer: 'onChange' }
  observers: [
    'onChange(value)'
    ]
  ready: ->
    
  onPickedColor: (ev) -> @value = ev.target.value
  onSlider: -> @value = @immediateSlider
  goWhite: -> @value = "#ffffff"
  goBlack: -> @value = "#000000"
  onChange: (value) ->
    @lastSent = [[@device, @deviceAttr.uri, value]]
    @resend()
  resend: ->
    window.gather(@lastSent)
  clear: ->
    if @deviceAttr.useColor
      @value = '#000000'
    else
      @value = @immediateSlider = 0

Polymer
  is: "light9-live-device-control"
  properties:
    graph: { type: Object, notify: true }
    uri: { type: String, notify: true }
    deviceClass: { type: String, notify: true }
    deviceAttrs: { type: Array, notify: true }
    bgStyle: { type: String, computed: '_bgStyle(deviceClass)' }
  observers: [
    'onGraph(graph)'
    ]
  _bgStyle: (deviceClass) ->
    hash = 0
    for i in [(deviceClass.length-10)...deviceClass.length]
        hash += deviceClass.charCodeAt(i)
    hue = (hash * 8) % 360
    accent = "hsl(#{hue}, 49%, 22%)"
    "background: linear-gradient(to right, rgba(31,31,31,0) 50%, #{accent} 100%);"
  onGraph: ->
    @graph.runHandler(@update.bind(@), "#{@uri} update")
  update: ->
    U = (x) => @graph.Uri(x)
    
    @deviceClass = @graph.uriValue(@uri, U('rdf:type'))
    
    @deviceAttrs = []
    for da in _.unique(_.sortBy(@graph.objects(@deviceClass, U(':deviceAttr'))))
      dataType = @graph.uriValue(da, U(':dataType'))
      daRow = {
        uri: da
        dataType: dataType
        showColorPicker: dataType == U(':color')
        }
      if dataType == 'http://light9.bigasterisk.com/color'
        daRow.useColor = true

      else if dataType == U(':choice')
        daRow.useChoice = true
        choiceUris = _.sortBy(@graph.objects(da, U(':choice')))
        daRow.choices = ({uri: x, label: @graph.labelOrTail(x)} for x in choiceUris)
        daRow.choiceSize = Math.min(choiceUris.length + 1, 10)
      else
        daRow.useSlider = true
        daRow.max = 1
        if dataType == U(':angle')
          # varies
          daRow.max = 1

      @push('deviceAttrs', daRow)

    
Polymer
  is: "light9-live-controls"
  properties:
    graph: { type: Object, notify: true }
    client: { type: Object, notify: true }
    devices: { type: Array, notify: true }
    currentSettings: { type: Object, notify: true } # dev+attr: [dev, attr, value]
    effectPreview: { type: String, notify: true }
    newEffectName: { type: String, notify: true }
  observers: [
    'onGraph(graph)'
    ]
  ready: ->
    @currentSettings = {}
    @effectPreview = JSON.stringify({})
    window.gather = (sent) =>
      [dev, devAttr, value] = sent[0]
      key = dev + " " + devAttr
      # this is a bug for zoom=0, since collector will default it to
      # stick at the last setting if we don't explicitly send the
      # 0. rx/ry similar though not the exact same deal because of
      # their remap.
      if value == 0 or value == '#000000'
        delete @currentSettings[key]
      else
        @currentSettings[key] = [dev, devAttr, value]
      @effectPreview = JSON.stringify(v for k,v of @currentSettings)

      @debounce('send', @sendAll.bind(@), 2)

  currentSettingsList: -> (v for k,v of @currentSettings)
      
  sendAll: ->
    @client.send(@currentSettingsList())
      
  saveNewEffect: ->
    uriName = @newEffectName.replace(/[^a-zA-Z0-9_]/g, '')
    return if not uriName.length

    U = (x) => @graph.Uri(x)

    effectUri = U(":effect") + "/#{uriName}"
    ctx = U("http://light9.bigasterisk.com/show/dance2017/effect/#{uriName}")
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: ctx}

    addQuads = [
      quad(effectUri, U('rdf:type'), U(':Effect'))
      quad(effectUri, U('rdfs:label'), @graph.Literal(@newEffectName))
      quad(effectUri, U(':publishAttr'), U(':strength'))
      ]
    settings = @graph.nextNumberedResources(effectUri + '_set', @currentSettingsList().length)
    for row in @currentSettingsList()
      if row[2] == 0 or row[2] == '#000000'
        continue
      setting = settings.shift()
      addQuads.push(quad(effectUri, U(':setting'), setting))
      addQuads.push(quad(setting, U(':device'), row[0]))
      addQuads.push(quad(setting, U(':deviceAttr'), row[1]))
      scaledAttributeTypes = [U(':color'), U(':brightness'), U(':uv')]
      value = if typeof(row[2]) == 'number'
          @graph.LiteralRoundedFloat(row[2])
        else
          @graph.Literal(row[2])
      settingType = if row[1] in scaledAttributeTypes then U(':scaledValue') else U(':value')
      addQuads.push(quad(setting, settingType, value))
      
    patch = {addQuads: addQuads, delQuads: []}
    log('save', patch)
    @graph.applyAndSendPatch(patch)
    @newEffectName = ''

  onGraph: ->
    @graph.runHandler(@update.bind(@))
  resendAll: ->
    for llc in @getElementsByTagName("light9-live-control")
      llc.resend()
  clearAll: ->
    for llc in @getElementsByTagName("light9-live-control")
      llc.clear()
    
  update: ->
    U = (x) => @graph.Uri(x)

    @set('devices', [])
    for dc in _.sortBy(@graph.subjects(U('rdf:type'), U(':DeviceClass')))
      for dev in _.sortBy(@graph.subjects(U('rdf:type'), dc))
        @push('devices', {uri: dev})
