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
  onChange: (lev) ->
    @client.send([[@device, @deviceAttr.uri, lev]])
  
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
            dev), deviceClass: dc}
        row.deviceAttrs = []
        for da in _.sortBy(@graph.objects(dc, U(':deviceAttr')))
          dataType = @graph.uriValue(da, U(':dataType'))
          daRow = {
            uri: da
            dataType: dataType
            showColorPicker: dataType == U(':color')
            }
          if da == 'http://light9.bigasterisk.com/color'
            daRow.useColor = true
            daRow.useSlider = false
          else
            daRow.useColor = false
            daRow.useSlider = true
            daRow.max = 1
            if dataType == U(':angle')
              # varies
              daRow.max = 360
          
          row.deviceAttrs.push(daRow)
        
        @push('devices', row)