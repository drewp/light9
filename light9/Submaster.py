from __future__ import division
import os, logging, time
from rdflib import Graph, RDF
from rdflib import RDFS, Literal, BNode
from light9.namespaces import L9, XSD
from light9.TLUtility import dict_scale, dict_max
from light9 import showconfig
from light9.Patch import resolve_name, get_dmx_channel, get_channel_uri, reload_data
from louie import dispatcher
from light9.rdfdb.patch import Patch
log = logging.getLogger('submaster')

class Submaster(object):
    """mapping of channels to levels"""
    def __init__(self, name, levels):
        """this sub has a name just for debugging. It doesn't get persisted.
        See PersistentSubmaster.

        levels is a dict
        """
        self.name = name
        self.levels = levels

        self.temporary = True

        if not self.temporary:
            # obsolete
            dispatcher.connect(log.error, 'reload all subs')

        #log.debug("%s initial levels %s", self.name, self.levels)

    def _editedLevels(self):
        pass

    def set_level(self, channelname, level, save=True):
        self.levels[resolve_name(channelname)] = level
        self._editedLevels()

    def set_all_levels(self, leveldict):
        self.levels.clear()
        for k, v in leveldict.items():
            # this may call _editedLevels too many times
            self.set_level(k, v, save=0)

    def get_levels(self):
        return self.levels

    def no_nonzero(self):
        return all(v == 0 for v in self.levels.itervalues())

    def __mul__(self, scalar):
        return Submaster("%s*%s" % (self.name, scalar),
                         levels=dict_scale(self.levels, scalar))
    __rmul__ = __mul__
    def max(self, *othersubs):
        return sub_maxes(self, *othersubs)

    def __add__(self, other):
        return self.max(other)

    def ident(self):
        return (self.name, tuple(sorted(self.levels.items())))

    def __repr__(self):
        items = getattr(self, 'levels', {}).items()
        items.sort()
        levels = ' '.join(["%s:%.2f" % item for item in items])
        return "<'%s': [%s]>" % (getattr(self, 'name', 'no name yet'), levels)

    def __cmp__(self, other):
        # not sure how useful this is
        if not isinstance(other, Submaster):
            return -1
        return cmp(self.ident(), other.ident())

    def __hash__(self):
        return hash(self.ident())

    def get_dmx_list(self):
        leveldict = self.get_levels() # gets levels of sub contents

        levels = []
        for k, v in leveldict.items():
            if v == 0:
                continue
            try:
                dmxchan = get_dmx_channel(k) - 1
            except ValueError:
                log.error("error trying to compute dmx levels for submaster %s"
                          % self.name)
                raise
            if dmxchan >= len(levels):
                levels.extend([0] * (dmxchan - len(levels) + 1))
            levels[dmxchan] = max(v, levels[dmxchan])

        return levels

    def normalize_patch_names(self):
        """Use only the primary patch names."""
        # possibly busted -- don't use unless you know what you're doing
        self.set_all_levels(self.levels.copy())

    def get_normalized_copy(self):
        """Get a copy of this sumbaster that only uses the primary patch
        names.  The levels will be the same."""
        newsub = Submaster("%s (normalized)" % self.name, {})
        newsub.set_all_levels(self.levels)
        return newsub

    def crossfade(self, othersub, amount):
        """Returns a new sub that is a crossfade between this sub and
        another submaster.

        NOTE: You should only crossfade between normalized submasters."""
        otherlevels = othersub.get_levels()
        keys_set = {}
        for k in self.levels.keys() + otherlevels.keys():
            keys_set[k] = 1
        all_keys = keys_set.keys()

        xfaded_sub = Submaster("xfade", {})
        for k in all_keys:
            xfaded_sub.set_level(k,
                                 linear_fade(self.levels.get(k, 0),
                                             otherlevels.get(k, 0),
                                             amount))

        return xfaded_sub

class PersistentSubmaster(Submaster):
    def __init__(self, graph, uri):
        if uri is None:
            raise TypeError("uri must be URIRef")
        self.graph, self.uri = graph, uri
        self.graph.addHandler(self.setName)
        self.graph.addHandler(self.setLevels)
        Submaster.__init__(self, self.name, self.levels)
        self.temporary = False

    def ident(self):
        return self.uri

    def _editedLevels(self):
        self.save()

    def changeName(self, newName):
        self.graph.patchObject(self.uri, self.uri, RDFS.label, Literal(newName))
        
    def setName(self):
        log.info("sub update name %s %s", self.uri, self.graph.label(self.uri))
        self.name = self.graph.label(self.uri)

    def setLevels(self):
        log.debug("sub update levels")
        oldLevels = getattr(self, 'levels', {}).copy()
        self.setLevelsFromGraph()
        if oldLevels != self.levels:
            log.debug("sub %s changed" % self.name)
            # dispatcher too? this would help subcomposer
            dispatcher.send("sub levels changed", sub=self)

    def setLevelsFromGraph(self):
        if hasattr(self, 'levels'):
            self.levels.clear()
        else:
            self.levels = {}
        for lev in self.graph.objects(self.uri, L9['lightLevel']):
            log.debug(" lightLevel %s %s", self.uri, lev)
            chan = self.graph.value(lev, L9['channel'])

            val = self.graph.value(lev, L9['level'])
            if val is None:
                # broken lightLevel link- may be from someone deleting channels
                log.warn("sub %r has lightLevel %r with channel %r "
                         "and level %r" % (self.uri, lev, chan, val))
                continue
            log.debug("   new val %r", val)
            if val == 0:
                continue
            name = self.graph.label(chan)
            if not name:
                log.error("sub %r has channel %r with no name- "
                          "leaving out that channel" % (self.name, chan))
                continue
            try:
                self.levels[name] = float(val)
            except:
                log.error("name %r val %r" % (name, val))
                raise

    def _saveContext(self):
        """the context in which we should save all the lightLevel triples for
        this sub"""
        typeStmt = (self.uri, RDF.type, L9['Submaster'])
        with self.graph.currentState(tripleFilter=typeStmt) as current:
            try:
                log.debug("submaster's type statement is in %r so we save there" %
                          list(current.contextsForStatement(typeStmt)))
                ctx = current.contextsForStatement(typeStmt)[0]
            except IndexError:
                log.info("declaring %s to be a submaster" % self.uri)
                ctx = self.uri
                self.graph.patch(Patch(addQuads=[
                    (self.uri, RDF.type, L9['Submaster'], ctx),
                    ]))

        return ctx

    def editLevel(self, chan, newLevel):
        self.graph.patchMapping(self._saveContext(),
                                subject=self.uri, predicate=L9['lightLevel'],
                                nodeClass=L9['ChannelSetting'],
                                keyPred=L9['channel'], newKey=chan,
                                valuePred=L9['level'],
                                newValue=Literal(newLevel))

    def clear(self):
        """set all levels to 0"""
        with self.graph.currentState() as g:
            levs = list(g.objects(self.uri, L9['lightLevel']))
        for lev in levs:
            self.graph.removeMappingNode(self._saveContext(), lev)

    def allQuads(self):
        """all the quads for this sub"""
        quads = []
        with self.graph.currentState() as current:
            quads.extend(current.quads((self.uri, None, None)))
            for s,p,o,c in quads:
                if p == L9['lightLevel']:
                    quads.extend(current.quads((o, None, None)))
        return quads


    def save(self):
        raise NotImplementedError("obsolete?")
        if self.temporary:
            log.info("not saving temporary sub named %s",self.name)
            return

        graph = Graph()
        subUri = L9['sub/%s' % self.name]
        graph.add((subUri, RDFS.label, Literal(self.name)))
        for chan in self.levels.keys():
            try:
                chanUri = get_channel_uri(chan)
            except KeyError:
                log.error("saving dmx channels with no :Channel node "
                          "is not supported yet. Give channel %s a URI "
                          "for it to be saved. Omitting this channel "
                          "from the sub." % chan)
                continue
            lev = BNode()
            graph.add((subUri, L9['lightLevel'], lev))
            graph.add((lev, L9['channel'], chanUri))
            graph.add((lev, L9['level'],
                       Literal(self.levels[chan], datatype=XSD['decimal'])))

        graph.serialize(showconfig.subFile(self.name), format="nt")


def linear_fade(start, end, amount):
    """Fades between two floats by an amount.  amount is a float between
    0 and 1.  If amount is 0, it will return the start value.  If it is 1,
    the end value will be returned."""
    level = start + (amount * (end - start))
    return level

def sub_maxes(*subs):
    nonzero_subs = [s for s in subs if not s.no_nonzero()]
    name = "max(%s)" % ", ".join([repr(s) for s in nonzero_subs])
    return Submaster(name,
                     levels=dict_max(*[sub.levels for sub in nonzero_subs]))

def combine_subdict(subdict, name=None, permanent=False):
    """A subdict is { Submaster objects : levels }.  We combine all
    submasters first by multiplying the submasters by their corresponding
    levels and then max()ing them together.  Returns a new Submaster
    object.  You can give it a better name than the computed one that it
    will get or make it permanent if you'd like it to be saved to disk.
    Serves 8."""
    scaledsubs = [sub * level for sub, level in subdict.items()]
    maxes = sub_maxes(*scaledsubs)
    if name:
        maxes.name = name
    if permanent:
        maxes.temporary = False

    return maxes

class Submasters(object):
    "Collection o' Submaster objects"
    def __init__(self, graph):
        self.submasters = {} # uri : Submaster
        self.graph = graph

        graph.addHandler(self.findSubs)

    def findSubs(self):
        current = set()

        for s in self.graph.subjects(RDF.type, L9['Submaster']):
            if self.graph.contains((s, RDF.type, L9['LocalSubmaster'])):
                continue
            log.debug("found sub %s", s)
            if s not in self.submasters:
                sub = self.submasters[s] = PersistentSubmaster(self.graph, s)
                dispatcher.send("new submaster", sub=sub)
            current.add(s)
        for s in set(self.submasters.keys()) - current:
            del self.submasters[s]
            dispatcher.send("lost submaster", subUri=s)
        log.info("findSubs finished, %s subs", len(self.submasters))

    def get_all_subs(self):
        "All Submaster objects"
        l = self.submasters.items()
        l.sort()
        l = [x[1] for x in l]
        songs = []
        notsongs = []
        for s in l:
            if s.name and s.name.startswith('song'):
                songs.append(s)
            else:
                notsongs.append(s)
        combined = notsongs + songs

        return combined

    def get_sub_by_uri(self, uri):
        return self.submasters[uri]

    def get_sub_by_name(self, name):
        return get_sub_by_name(name, self)

# a global instance of Submasters, created on demand
_submasters = None

def get_global_submasters(graph):
    """
    Get (and make on demand) the global instance of
    Submasters. Cached, but the cache is not correctly using the graph
    argument. The first graph you pass will stick in the cache.
    """
    global _submasters
    if _submasters is None:
        _submasters = Submasters(graph)
    return _submasters

def get_sub_by_name(name, submasters=None):
    """name is a channel or sub nama, submasters is a Submasters object.
    If you leave submasters empty, it will use the global instance of
    Submasters."""
    if not submasters:
        submasters = get_global_submasters()

    # get_all_sub_names went missing. needs rework
    #if name in submasters.get_all_sub_names():
    #    return submasters.get_sub_by_name(name)

    try:
        val = int(name)
        s = Submaster("#%d" % val, levels={val : 1.0})
        return s
    except ValueError:
        pass

    try:
        subnum = get_dmx_channel(name)
        s = Submaster("'%s'" % name, levels={subnum : 1.0})
        return s
    except ValueError:
        pass

    # make an error sub
    return Submaster('%s' % name, levels=ValueError)

if __name__ == "__main__":
    reload_data()
    s = Submasters()
    print s.get_all_subs()
    if 0: # turn this on to normalize all subs
        for sub in s.get_all_subs():
            print "before", sub
            sub.normalize_patch_names()
            sub.save()
            print "after", sub
