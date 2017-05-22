"""
Data structure and convertors for a table of (device,attr,value)
rows. These might be effect attrs ('strength'), device attrs ('rx'),
or output attrs (dmx channel).
"""
import decimal
from rdflib import URIRef, Literal
from light9.namespaces import RDF, L9, DEV
from light9.rdfdb.patch import Patch


def getVal(graph, subj):
    lit = graph.value(subj, L9['value']) or graph.value(subj, L9['scaledValue'])
    ret = lit.toPython()
    if isinstance(ret, decimal.Decimal):
        ret = float(ret)
    return ret

class _Settings(object):
    """
    default values are 0. Internal rep must not store zeros or some
    comparisons will break.
    """
    def __init__(self, graph, settingsList):
        self.graph = graph # for looking up all possible attrs
        self._compiled = {} # dev: { attr: val }
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
    def fromVector(cls, graph, vector):
        compiled = {}
        for (d, a), v in zip(cls(graph, [])._vectorKeys(), vector):
            compiled.setdefault(d, {})[a] = v
        return cls._fromCompiled(graph, compiled)

    def _delZeros(self):
        for dev, av in self._compiled.items():
            for attr, val in av.items():
                if val == 0:
                    del av[attr]
            if not av:
                del self._compiled[dev]
        
    def __hash__(self):
        itemed = tuple([(d, tuple([(a, v) for a, v in sorted(av.items())]))
                        for d, av in sorted(self._compiled.items())])
        return hash(itemed)

    def __eq__(self, other):
        if not issubclass(other.__class__, self.__class__):
            raise TypeError("can't compare %r to %r" % (self.__class__, other.__class__))
        return self._compiled == other._compiled

    def __ne__(self, other):
        return not self == other


    def __repr__(self):
        words = []
        def accum():
            for dev, av in self._compiled.iteritems():
                for attr, val in av.iteritems():
                    words.append('%s.%s=%g' % (dev.rsplit('/')[-1],
                                               attr.rsplit('/')[-1],
                                               val))
                    if len(words) > 5:
                        words.append('...')
                        return
        accum()
        return '<%s %s>' % (self.__class__.__name__, ' '.join(words))
        
    def getValue(self, dev, attr):
        return self._compiled.get(dev, {}).get(attr, 0)

    def _vectorKeys(self):
        """stable order of all the dev,attr pairs for this type of settings"""
        raise NotImplementedError

    def asList(self):
        """old style list of (dev, attr, val) tuples"""
        out = []
        for dev, av in self._compiled.iteritems():
            for attr, val in av.iteritems():
                out.append((dev, attr, val))
        return out

    def devices(self):
        return self._compiled.keys()
        
    def toVector(self):
        out = []
        for dev, attr in self._vectorKeys():
            out.append(self._compiled.get(dev, {}).get(attr, 0))
        return out

    def byDevice(self):
        for dev, av in self._compiled.iteritems():
            yield dev, self.__class__._fromCompiled(self.graph, {dev: av})

    def ofDevice(self, dev):
        return self.__class__._fromCompiled(self.graph,
                                            {dev: self._compiled.get(dev, {})})
        
    def distanceTo(self, other):
        raise NotImplementedError
        dist = 0
        for key in set(attrs1).union(set(attrs2)):
            if key not in attrs1 or key not in attrs2:
                dist += 999
            else:
                dist += abs(attrs1[key] - attrs2[key])
        return dist

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
            settingType = L9['scaledValue'] if attr in scaledAttributeTypes else L9['value']
            add.extend([
                (setting, L9['device'], dev, ctx),
                (setting, L9['deviceAttr'], attr, ctx),
                (setting, settingType, Literal(val), ctx),
                ])
            settingsSubgraphCache.add(setting)
            
        return add


class DeviceSettings(_Settings):
    def _vectorKeys(self):
        with self.graph.currentState() as g:
            devs = set() # devclass, dev
            for dc in g.subjects(RDF.type, L9['DeviceClass']):
                for dev in g.subjects(RDF.type, dc):
                    devs.add((dc, dev))

            keys = []
            for dc, dev in sorted(devs):
                for attr in sorted(g.objects(dc, L9['deviceAttr'])):
                    keys.append((dev, attr))
        return keys
    
