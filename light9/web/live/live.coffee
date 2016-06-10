
Polymer
  is: 'light9-live-control'
  properties:
    client: { type: Object }
    device: { type: String }
    attr: { type: String }
    max: { type: Number, value: 1 }
    immediateSlider: { notify: true, observer: 'onChange' }
    useSlider: { type: Boolean, computed: '_useSlider(attr)' }
    useColor: { type: Boolean, computed: '_useColor(attr)' }
    pickedColor: { observer: 'onPickedColor' }
  ready: ->
  onPickedColor: (ev) ->
    @onChange ev.target.value
  onChange: (lev) ->
    @client.send([[@device, @attr, lev]])
  _useSlider: (attr) ->
    attr != 'http://light9.bigasterisk.com/color'
  _useColor: (attr) ->
    attr == 'http://light9.bigasterisk.com/color'
