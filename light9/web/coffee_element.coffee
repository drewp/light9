# Polymer seems to need static getters for 'observers' and
# 'properties', not just static attributes, though I don't know how it
# can even tell the difference.
#
# This workaround is to use names like '@getter_properties' in the
# class then register with this function that fixes them.
# 
# Also see http://coffeescript.org/#unsupported-get-set
window.coffeeElementSetup = (cls) ->
  for attr in ['properties', 'observers']
    val = cls['getter_' + attr]
    if val?
      do (val) ->
        Object.defineProperty(cls, attr, {get: ( -> val)})  
  customElements.define(cls.is, cls)
