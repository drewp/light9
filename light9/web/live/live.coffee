log = console.log

Polymer
  is: 'light9-live-control'
  properties:
    client: { type: Object }
    device: { type: String }
    deviceAttr: { type: Object }
    max: { type: Number, value: 1 }
    value: { type: Object, notify: true }
    
    immediateSlider: { notify: true, observer: 'onSlider' }
    pickedColor: { observer: 'onPickedColor' }
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
    @client.send(@lastSent)
    window.gather(@lastSent)
  clear: ->
    if @deviceAttr.useColor
      @value = '#000000'
    else
      @value = 0
      
  
Polymer
  is: "light9-live-controls"
  properties:
    graph: { type: Object, notify: true }
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
      return if value == 0
      @currentSettings[dev + " " + devAttr] = [dev, devAttr, value]
      @effectPreview = JSON.stringify(v for k,v of @currentSettings)
  saveNewEffect: ->
    return if not @newEffectName.length

    U = (x) -> @graph.Uri(x)

    effectUri = U(":effect") + "/#{@newEffectName}"
    ctx = U('http://light9.bigasterisk.com/show/dance2016/effect')
    quad = (s, p, o) => {subject: s, predicate: p, object: o, graph: ctx}

    addQuads = [
      quad(effectUri, U('rdf:type'), U(':Effect'))
      quad(effectUri, U('rdfs:label'), @graph.Literal(@newEffectName))
      quad(effectUri, U(':publishAttr'), U(':strength'))
      ]
    settings = @graph.nextNumberedResources(effectUri + '_set', Object.keys(@currentSettings).length)
    for _, row of @currentSettings
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

  onGraph: ->
    @graph.runHandler(@update.bind(@))
  resendAll: ->
    for llc in @getElementsByTagName("light9-live-control")
      llc.resend()
  clearAll: ->
    for llc in @getElementsByTagName("light9-live-control")
      llc.clear()
    
  update: ->
    U = (x) -> @graph.Uri(x)

    @set('devices', [])
    for dc in _.sortBy(@graph.subjects(U('rdf:type'), U(':DeviceClass')))
      for dev in _.sortBy(@graph.subjects(U('rdf:type'), dc))
        row = {uri: dev, label: (try
            @graph.stringValue(dev, U('rdfs:label'))
          catch
            words = dev.split('/')
            words[words.length-1]
            ), deviceClass: dc}
        row.deviceAttrs = []
        for da in _.sortBy(@graph.objects(dc, U(':deviceAttr')))
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
            daRow.choices = @graph.objects(da, U(':choice'))
          else

            daRow.useSlider = true
            daRow.max = 1
            if dataType == U(':angle')
              # varies
              daRow.max = 1
          
          row.deviceAttrs.push(daRow)
        
        @push('devices', row)