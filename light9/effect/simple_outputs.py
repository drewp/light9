from __future__ import division
import traceback
from light9.namespaces import L9, RDF
from light9.effect.scale import scale


class SimpleOutputs(object):

    def __init__(self, graph):
        self.graph = graph

        # effect : [(dev, attr, value, isScaled)]
        self.effectOutputs = {}

        self.graph.addHandler(self.updateEffectsFromGraph)

    def updateEffectsFromGraph(self):
        for effect in self.graph.subjects(RDF.type, L9['Effect']):
            settings = []
            for setting in self.graph.objects(effect, L9['setting']):
                settingValues = dict(self.graph.predicate_objects(setting))
                try:
                    d = settingValues.get(L9['device'], None)
                    a = settingValues.get(L9['deviceAttr'], None)
                    v = settingValues.get(L9['value'], None)
                    sv = settingValues.get(L9['scaledValue'], None)
                    if not (bool(v) ^ bool(sv)):
                        raise NotImplementedError('no value for %s' % setting)
                    if d is None:
                        raise TypeError('no device on %s' % effect)
                    if a is None:
                        raise TypeError('no attr on %s' % effect)
                except Exception:
                    traceback.print_exc()
                    continue

                settings.append((d, a, v if v is not None else sv, bool(sv)))

            if settings:
                self.effectOutputs[effect] = settings
            # also have to read eff :effectAttr [ :tint x; :tintStrength y ]

    def values(self, effect, strength, colorScale):
        out = {}
        for dev, devAttr, value, isScaled in self.effectOutputs.get(effect, []):
            if isScaled:
                value = scale(value, strength)
            if colorScale is not None and devAttr == L9['color']:
                value = scale(value, colorScale)
            out[(dev, devAttr)] = value
        return out
