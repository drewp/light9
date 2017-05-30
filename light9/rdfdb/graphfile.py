import logging, traceback, os, time
from twisted.python.filepath import FilePath
from twisted.internet import reactor
from twisted.internet.inotify import humanReadableMask
from rdflib import Graph, RDF
from light9.rdfdb.patch import Patch
from light9.rdfdb.rdflibpatch import inContext

log = logging.getLogger('graphfile')
iolog = logging.getLogger('io')

def patchN3SerializerToUseLessWhitespace(cutColumn=65):
    # todo: make a n3serializer subclass with whitespace settings
    from rdflib.plugins.serializers.turtle import TurtleSerializer, OBJECT
    originalWrite = TurtleSerializer.write
    def write(self, s):
        lines = s.split('\n')
        if len(lines) > 1:
            self._column = len(lines[-1])
        else:
            self._column += len(lines[0])
        return originalWrite(self, s)
    TurtleSerializer.write = write
    def predicateList(self, subject, newline=False):
        properties = self.buildPredicateHash(subject)
        propList = self.sortProperties(properties)
        if len(propList) == 0:
            return
        self.verb(propList[0], newline=newline)
        self.objectList(properties[propList[0]])
        for predicate in propList[1:]:
            self.write(';')
            # can't do proper wrapping since we don't know how much is coming
            if self._column > cutColumn:
                self.write('\n' + self.indent(1))
            self.verb(predicate, newline=False)
            self.objectList(properties[predicate])
    def objectList(self, objects):
        count = len(objects)
        if count == 0:
            return
        depthmod = (count == 1) and 0 or 1
        self.depth += depthmod
        self.path(objects[0], OBJECT)
        for obj in objects[1:]:
            self.write(', ')
            self.path(obj, OBJECT, newline=True)
        self.depth -= depthmod

    originalStatement = TurtleSerializer.statement
    def statement(self, subject):
        if list(self.store.triples((subject, RDF.type, None))):
            self.write('\n')
        originalStatement(self, subject)
        return False         #  suppress blank line for 'minor' statements
    TurtleSerializer.statement = statement
    TurtleSerializer.predicateList = predicateList
    TurtleSerializer.objectList = objectList

patchN3SerializerToUseLessWhitespace()

class GraphFile(object):
    """
    one rdf file that we read from, write to, and notice external changes to
    """
    def __init__(self, notifier, path, uri, patch, getSubgraph, globalPrefixes, ctxPrefixes):
        """
        uri is the context for the triples in this file. We assume
        sometimes that we're the only ones with triples in this
        context.
        
        this does not include an initial reread() call

        Prefixes are mutable dicts. The caller may add to them later.
        """
        self.path, self.uri = path, uri
        self.patch, self.getSubgraph = patch, getSubgraph

        self.lastWriteTimestamp = 0 # mtime from the last time _we_ wrote

        self.globalPrefixes = globalPrefixes
        self.ctxPrefixes = ctxPrefixes
        self.readPrefixes = {}
        
        if not os.path.exists(path):
            # can't start notify until file exists
            try:
                os.makedirs(os.path.dirname(path))
            except OSError:
                pass
            f = open(path, "w")
            f.write("#new\n")
            f.close()
            iolog.info("%s created", path)
            # this was supposed to cut out some extra reads but it
            # didn't work:
            self.lastWriteTimestamp = os.path.getmtime(path)


        self.flushDelay = 2 # seconds until we have to call flush() when dirty
        self.writeCall = None # or DelayedCall

        self.notifier = notifier
        self.addWatch()
        
    def addWatch(self):

        # emacs save comes in as IN_MOVE_SELF, maybe
        
        # I was hoping not to watch IN_CHANGED and get lots of
        # half-written files, but emacs doesn't close its files after
        # a write, so there's no other event. I could try to sleep
        # until after all the writes are done, but I think the only
        # bug left is that we'll retry too agressively on a file
        # that's being written

        from twisted.internet.inotify import IN_CLOSE_WRITE, IN_MOVED_FROM, IN_MODIFY, IN_DELETE, IN_DELETE_SELF, IN_CHANGED

        log.info("add watch on %s", self.path)
        self.notifier.watch(FilePath(self.path), callbacks=[self.notify])
        
    def notify(self, notifier, filepath, mask):
        try:
            maskNames = humanReadableMask(mask)
            if maskNames[0] == 'delete_self':
                if not filepath.exists():
                    log.info("%s delete_self", filepath)
                    self.fileGone()
                    return
                else:
                    log.warn("%s delete_self event but file is here. "
                             "probably a new version moved in",
                             filepath)

            # we could filter these out in the watch() call, but I want
            # the debugging
            if maskNames[0] in ['open', 'access', 'close_nowrite', 'attrib']:
                log.debug("%s %s event, ignoring" % (filepath, maskNames))
                return

            try:
                if filepath.getModificationTime() == self.lastWriteTimestamp:
                    log.debug("%s changed, but we did this write", filepath)
                    return
            except OSError as e:
                log.error("%s: %r" % (filepath, e))
                # getting OSError no such file, followed by no future reads
                reactor.callLater(.5, self.addWatch) # ?

                return

            log.info("reread %s because of %s event", filepath, maskNames)

            self.reread()
        except Exception:
            traceback.print_exc()

    def fileGone(self):
        """
        our file is gone; remove the statements from that context
        """
        myQuads = [(s,p,o,self.uri) for s,p,o in self.getSubgraph(self.uri)]
        log.debug("dropping all statements from context %s", self.uri)
        if myQuads:
            self.patch(Patch(delQuads=myQuads), dueToFileChange=True)
            
    def reread(self):
        """update the graph with any diffs from this file

        n3 parser fails on "1.e+0" even though rdflib was emitting that itself
        """
        old = self.getSubgraph(self.uri)
        new = Graph()
        try:
            contents = open(self.path).read()
            if contents.startswith("#new"):
                log.debug("%s ignoring empty contents of my new file", self.path)
                # this is a new file we're starting, and we should not
                # patch our graph as if it had just been cleared. We
                # shouldn't even be here reading this, but
                # lastWriteTimestamp didn't work.
                return

            new.parse(location=self.path, format='n3')
            self.readPrefixes = dict(new.namespaces())
        except SyntaxError as e:
            print e
            traceback.print_exc()
            log.error("%s syntax error", self.path)
            # todo: likely bug- if a file has this error upon first
            # read, I think we don't retry it right.
            return
        except IOError as e:
            log.error("%s rereading %s: %r", self.path, self.uri, e)
            return

        old = inContext(old, self.uri)
        new = inContext(new, self.uri)

        p = Patch.fromDiff(old, new)
        if p:
            log.debug("%s applying patch for changes in file", self.path)
            self.patch(p, dueToFileChange=True)
        else:
            log.debug("old == new after reread of %s", self.path)

    def dirty(self, graph):
        """
        there are new contents to write to our file
        
        graph is the rdflib.Graph that contains the contents of the
        file. It is allowed to change. Note that dirty() will probably
        do the save later when the graph might be different.
        
        after a timer has passed, write it out. Any scheduling issues
        between files? i don't think so. the timer might be kind of
        huge, and then we might want to take a hint from a client that
        it's a good time to save the files that it was editing, like
        when the mouse moves out of the client's window and might be
        going towards a text file editor
        
        """
        log.info("%s dirty, needs write", self.path)

        self.graphToWrite = graph
        if self.writeCall:
            self.writeCall.reset(self.flushDelay)
        else:
            self.writeCall = reactor.callLater(self.flushDelay, self.flush)

    def flush(self):
        self.writeCall = None

        tmpOut = self.path + ".rdfdb-temp"
        f = open(tmpOut, 'w')
        t1 = time.time()
        for p, n in (self.globalPrefixes.items() +
                     self.readPrefixes.items() +
                     self.ctxPrefixes.items()):
            self.graphToWrite.bind(p, n)
        self.graphToWrite.serialize(destination=f, format='n3')
        serializeTime = time.time() - t1
        f.close()
        self.lastWriteTimestamp = os.path.getmtime(tmpOut)
        os.rename(tmpOut, self.path)
        iolog.info("%s rewrote in %.1f ms",
                   self.path, serializeTime * 1000)
        
    def __repr__(self):
        return "%s(path=%r, uri=%r, ...)" % (
            self.__class__.__name__, self.path, self.uri)
        
