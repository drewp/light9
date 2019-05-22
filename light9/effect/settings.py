"""
Data structure and convertors for a table of (device,attr,value)
rows. These might be effect attrs ('strength'), device attrs ('rx'),
or output attrs (dmx channel).
"""
import decimal
import numpy
from rdflib import URIRef, Literal
from light9.namespaces import RDF, L9, DEV
from rdfdb.patch import Patch
import logging
log = logging.getLogger('settings')
from light9.collector.device import resolve


def parseHex(h):
    if h[0] != '#': raise ValueError(h)
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def parseHexNorm(h):
    return [x / 255 for x in parseHex(h)]


def toHex(rgbFloat):
    return '#%02x%02x%02x' % tuple(
        max(0, min(255, int(v * 255))) for v in rgbFloat)


def getVal(graph, subj):
    lit = graph.value(subj, L9['value']) or graph.value(subj, L9['scaledValue'])
    ret = lit.toPython()
    if isinstance(ret, decimal.Decimal):
        ret = float(ret)
    return ret


class _Settings(object):
    """
    default values are 0 or '#000000'. Internal rep must not store zeros or some
    comparisons will break.
    """

    def __init__(self, graph, settingsList):
        self.graph = graph  # for looking up all possible attrs
        self._compiled = {}  # dev: { attr: val }; val is number or colorhex
        for row in settingsList:
            self._compiled.setdefault(row[0], {})[row[1]] = row[2]
        # self._compiled may not be final yet- see _fromCompiled
        self._delZeros()

    @classmethod
    def _fromCompiled(cls, graph, compiled):
        obj = cls(graph, [])
        obj._compiled = compiled
        obj._delZeros()
        return obj

    @classmethod
    def fromResource(cls, graph, subj):
        settingsList = []
        with graph.currentState() as g:
            for s in g.objects(subj, L9['setting']):
                d = g.value(s, L9['device'])
                da = g.value(s, L9['deviceAttr'])
                v = getVal(g, s)
                settingsList.append((d, da, v))
        return cls(graph, settingsList)

    @classmethod
    def fromVector(cls, graph, vector, deviceAttrFilter=None):
        compiled = {}
        i = 0
        for (d, a) in cls(graph, [])._vectorKeys(deviceAttrFilter):
            if a == L9['color']:
                v = toHex(vector[i:i + 3])
                i += 3
            else:
                v = vector[i]
                i += 1
            compiled.setdefault(d, {})[a] = v
        return cls._fromCompiled(graph, compiled)

    @classmethod
    def fromList(cls, graph, others):
        """note that others may have multiple values for an attr"""
        out = cls(graph, [])
        for s in others:
            if not isinstance(s, cls):
                raise TypeError(s)
            for row in s.asList():  # could work straight from s._compiled
                if row[0] is None:
                    raise TypeError('bad row %r' % (row,))
                dev, devAttr, value = row
                devDict = out._compiled.setdefault(dev, {})
                if devAttr in devDict:
                    value = resolve(dev, devAttr, [devDict[devAttr], value])
                devDict[devAttr] = value
        out._delZeros()
        return out

    @classmethod
    def fromBlend(cls, graph, others):
        """others is a list of (weight, Settings) pairs"""
        out = cls(graph, [])
        for weight, s in others:
            if not isinstance(s, cls):
                raise TypeError(s)
            for row in s.asList():  # could work straight from s._compiled
                if row[0] is None:
                    raise TypeError('bad row %r' % (row,))
                dd = out._compiled.setdefault(row[0], {})

                if isinstance(row[2], str):
                    prev = parseHexNorm(dd.get(row[1], '#000000'))
                    newVal = toHex(prev +
                                   weight * numpy.array(parseHexNorm(row[2])))
                else:
                    newVal = dd.get(row[1], 0) + weight * row[2]
                dd[row[1]] = newVal
        out._delZeros()
        return out

    def _zeroForAttr(self, attr):
        if attr == L9['color']:
            return '#000000'
        return 0.0

    def _delZeros(self):
        for dev, av in list(self._compiled.items()):
            for attr, val in list(av.items()):
                if val == self._zeroForAttr(attr):
                    del av[attr]
            if not av:
                del self._compiled[dev]

    def __hash__(self):
        itemed = tuple([(d, tuple([(a, v)
                                   for a, v in sorted(av.items())]))
                        for d, av in sorted(self._compiled.items())])
        return hash(itemed)

    def __eq__(self, other):
        if not issubclass(other.__class__, self.__class__):
            raise TypeError("can't compare %r to %r" %
                            (self.__class__, other.__class__))
        return self._compiled == other._compiled

    def __ne__(self, other):
        return not self == other

    def __bool__(self):
        return bool(self._compiled)

    def __repr__(self):
        words = []

        def accum():
            for dev, av in self._compiled.items():
                for attr, val in sorted(av.items()):
                    words.append(
                        '%s.%s=%s' %
                        (dev.rsplit('/')[-1], attr.rsplit('/')[-1], val))
                    if len(words) > 5:
                        words.append('...')
                        return

        accum()
        return '<%s %s>' % (self.__class__.__name__, ' '.join(words))

    def getValue(self, dev, attr):
        return self._compiled.get(dev, {}).get(attr, self._zeroForAttr(attr))

    def _vectorKeys(self, deviceAttrFilter=None):
        """stable order of all the dev,attr pairs for this type of settings"""
        raise NotImplementedError

    def asList(self):
        """old style list of (dev, attr, val) tuples"""
        out = []
        for dev, av in self._compiled.items():
            for attr, val in av.items():
                out.append((dev, attr, val))
        return out

    def devices(self):
        return list(self._compiled.keys())

    def toVector(self, deviceAttrFilter=None):
        out = []
        for dev, attr in self._vectorKeys(deviceAttrFilter):
            v = self.getValue(dev, attr)
            if attr == L9['color']:
                out.extend(parseHexNorm(v))
            else:
                out.append(v)
        return out

    def byDevice(self):
        for dev, av in self._compiled.items():
            yield dev, self.__class__._fromCompiled(self.graph, {dev: av})

    def ofDevice(self, dev):
        return self.__class__._fromCompiled(self.graph,
                                            {dev: self._compiled.get(dev, {})})

    def distanceTo(self, other):
        diff = numpy.array(self.toVector()) - other.toVector()
        d = numpy.linalg.norm(diff, ord=None)
        log.info('distanceTo %r - %r = %g', self, other, d)
        return d

    def statements(self, subj, ctx, settingRoot, settingsSubgraphCache):
        """
        settingRoot can be shared across images (or even wider if you want)
        """
        # ported from live.coffee
        add = []
        for i, (dev, attr, val) in enumerate(self.asList()):
            # hopefully a unique number for the setting so repeated settings converge
            settingHash = hash((dev, attr, val)) % 9999999
            setting = URIRef('%sset%s' % (settingRoot, settingHash))
            add.append((subj, L9['setting'], setting, ctx))
            if setting in settingsSubgraphCache:
                continue

            scaledAttributeTypes = [L9['color'], L9['brightness'], L9['uv']]
            settingType = L9[
                'scaledValue'] if attr in scaledAttributeTypes else L9['value']
            if not isinstance(val, URIRef):
                val = Literal(val)
            add.extend([
                (setting, L9['device'], dev, ctx),
                (setting, L9['deviceAttr'], attr, ctx),
                (setting, settingType, val, ctx),
            ])
            settingsSubgraphCache.add(setting)

        return add


class DeviceSettings(_Settings):

    def _vectorKeys(self, deviceAttrFilter=None):
        with self.graph.currentState() as g:
            devs = set()  # devclass, dev
            for dc in g.subjects(RDF.type, L9['DeviceClass']):
                for dev in g.subjects(RDF.type, dc):
                    devs.add((dc, dev))

            keys = []
            for dc, dev in sorted(devs):
                for attr in sorted(g.objects(dc, L9['deviceAttr'])):
                    key = (dev, attr)
                    if deviceAttrFilter and key not in deviceAttrFilter:
                        continue
                    keys.append(key)
        return keys
