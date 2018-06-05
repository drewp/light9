log = console.log

coffeeElementSetup(class Light9LiveControl extends Polymer.Element
  @is: 'light9-live-control'
  @getter_properties:
    device: { type: String }
    deviceAttr: { type: Object }
    max: { type: Number, value: 1 }
    value: { type: Object, notify: true }
    
    immediateSlider: { notify: true, observer: 'onSlider' }
    sliderWriteValue: { type: Number }
    pickedChoice: { observer: 'onChange' }
  @getter_observers: [
    'onChange(value)'
    ]
  ready: ->
    super.ready()
  onSlider: -> @value = @immediateSlider
  goBlack: -> @value = "#000000"
  onChange: (value) ->
    @lastSent = [[@device, @deviceAttr.uri, value]]
    @resend()
  resend: ->
    window.gather(@lastSent)
  clear: ->
    @pickedChoice = null
    @sliderWriteValue = 0
    if @deviceAttr.useColor
      @value = '#000000'
    else
      @value = @immediateSlider = 0
)

coffeeElementSetup(class Light9LiveDeviceControl extends Polymer.Element
  @is: "light9-live-device-control"
  @getter_properties:
    graph: { type: Object, notify: true }
    uri: { type: String, notify: true }
    deviceClass: { type: String, notify: true }
    deviceAttrs: { type: Array, notify: true }
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
  update: ->
    U = (x) => @graph.Uri(x)
    
    @deviceClass = @graph.uriValue(@uri, U('rdf:type'))
    
    @deviceAttrs = []
    for da in _.unique(@graph.sortedUris(@graph.objects(@deviceClass, U(':deviceAttr'))))
      dataType = @graph.uriValue(da, U(':dataType'))
      daRow = {
        uri: da
        dataType: dataType
        showColorPicker: dataType.equals(U(':color'))
        }
      if dataType.equals(U(':color'))
        daRow.useColor = true

      else if dataType.equals(U(':choice'))
        daRow.useChoice = true
        choiceUris = @graph.sortedUris(@graph.objects(da, U(':choice')))
        daRow.choices = ({uri: x, label: @graph.labelOrTail(x)} for x in choiceUris)
        daRow.choiceSize = Math.min(choiceUris.length + 1, 10)
      else
        daRow.useSlider = true
        daRow.max = 1
        if dataType.equals(U(':angle'))
          # varies
          daRow.max = 1

      @push('deviceAttrs', daRow)
  clear: ->
    for lc in @shadowRoot.querySelectorAll("light9-live-control")
      lc.clear()
    
)
    
coffeeElementSetup(class Light9LiveControls extends Polymer.Element
  @is: "light9-live-controls"
  @getter_properties:
    graph: { type: Object, notify: true }
    client: { type: Object, notify: true }
    devices: { type: Array, notify: true }
    currentSettings: { type: Object, notify: true } # dev+attr: [dev, attr, value]
    effectPreview: { type: String, notify: true }
    newEffectName: { type: String, notify: true }
    effect: { type: String, notify: true } # the one being edited, if any
  @getter_observers: [
    'onGraph(graph)'
    'onEffect(effect)'
    ]
  ready: ->
    super.ready()
    @currentSettings = {}
    @effectPreview = JSON.stringify({})

    @sendAllThrottled = _.throttle(@sendAll.bind(@), 30)
    
    window.gather = (sent) =>
      [dev, devAttr, value] = sent[0]
      key = dev.value + " " + devAttr.value
      # this is a bug for zoom=0, since collector will default it to
      # stick at the last setting if we don't explicitly send the
      # 0. rx/ry similar though not the exact same deal because of
      # their remap.
      if value == 0 or value == '#000000' or value == null or value == undefined
        delete @currentSettings[key]
      else
        @currentSettings[key] = [dev, devAttr, value]
      @effectPreview = JSON.stringify(v for k,v of @currentSettings)

      @sendAllThrottled()

  currentSettingsList: -> (v for k,v of @currentSettings)
      
  sendAll: ->
    @client.send(@currentSettingsList())

  valuePred: (attr) ->
    U = (x) => @graph.Uri(x)
    scaledAttributeTypes = [U(':color'), U(':brightness'), U(':uv')]
    if attr in scaledAttributeTypes then U(':scaledValue') else U(':value')

  onEffect: ->
    U = (x) => @graph.Uri(x)
    return unless @effect
    log('load', @effect)
    for s in @graph.objects(@effect, U(':setting'))
      dev = @graph.uriValue(s, U(':device'))
      devAttr = @graph.uriValue(s, U(':deviceAttr'))

      pred = @valuePred(devAttr)
      try
        value = @graph.floatValue(s, pred)
      catch
        value = @graph.stringValue(s, pred)
      log('got', devAttr, value)
      window.gather([[dev, devAttr, value]])
            
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
      value = if typeof(row[2]) == 'number'
          @graph.LiteralRoundedFloat(row[2])
        else
          @graph.Literal(row[2])
      addQuads.push(quad(setting, @valuePred(row[1]), value))
      
    patch = {addQuads: addQuads, delQuads: []}
    log('save', patch)
    @graph.applyAndSendPatch(patch)
    @newEffectName = ''

  onGraph: ->
    @graph.runHandler(@update.bind(@), 'controls')
    
  resendAll: ->
    for llc in @getElementsByTagName("light9-live-control")
      llc.resend()
      
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
    setTimeout((() => $('#deviceControls').isotope({
      # fitColumns would be nice, but it doesn't scroll vertically
      layoutMode: 'masonry',
      containerStyle: null
      })), 2000)
)