log = console.log

Polymer
  is: 'light9-live-control'
  properties:
    client: { type: Object }
    device: { type: String }
    deviceAttr: { type: Object }
    max: { type: Number, value: 1 }
    immediateSlider: { notify: true, observer: 'onChange' }
    pickedColor: { observer: 'onPickedColor' }
  ready: ->
  onPickedColor: (ev) ->
    @onChange ev.target.value
  goWhite: -> @onChange("#ffffff")
  goBlack: -> @onChange("#000000")
  onChange: (lev) ->
    @lastSent = [[@device, @deviceAttr.uri, lev]]
    @resend()
  resend: ->
    @client.send(@lastSent)
  
Polymer
  is: "light9-live-controls"
  properties:
    graph: { type: Object, notify: true }
    devices: { type: Array, notify: true }
  observers: [
    'onGraph(graph)'
    ]
  onGraph: ->
    @graph.runHandler(@update.bind(@))
  resendAll: ->
    for llc in @getElementsByTagName("light9-live-control")
      llc.resend()
  update: ->
    U = (x) -> @graph.Uri(x)

    @set('devices', [])
    for dc in _.sortBy(@graph.subjects(U('rdf:type'), U(':DeviceClass')))
      log('dc', dc)      
      for dev in _.sortBy(@graph.subjects(U('rdf:type'), dc))
        log('dev', dev)
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