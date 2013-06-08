import gtk, logging
from louie import dispatcher
from rdflib import URIRef
from light9 import Submaster
from light9.namespaces import L9
from light9.curvecalc.subterm import Subterm, Subexpr
log = logging.getLogger()

# inspired by http://www.daa.com.au/pipermail/pygtk/2008-August/015772.html
# keeping a ref to the __dict__ of the object stops it from getting zeroed
keep = []

class Subexprview(object):
    def __init__(self, graph, ownerSubterm):
        self.graph, self.ownerSubterm = graph, ownerSubterm

        self.box = gtk.HBox()

        self.entryBuffer = gtk.EntryBuffer("", -1)
        self.entry = gtk.Entry()
        self.error = gtk.Label("")

        self.box.pack_start(self.entry, expand=True)
        self.box.pack_start(self.error, expand=False)

        self.entry.set_buffer(self.entryBuffer)
        self.expr_changed()
        self.entryBuffer.connect("deleted-text", self.entry_changed)
        self.entryBuffer.connect("inserted-text", self.entry_changed)
        dispatcher.connect(self.expr_changed, "expr_changed",
                           sender=self.ownerSubterm)

        dispatcher.connect(self.exprError, "expr_error", sender=self.ownerSubterm)
        keep.append(self.__dict__)

    def exprError(self, exc):
        self.error.set_text(str(exc))
        
    def expr_changed(self):
        log.warn("skip expr_changed")
        return
        e = str(self.subexpr.expr)
        if e != self.entryBuffer.get_text():
            self.entryBuffer.set_text(e, len(e))
            
    def entry_changed(self, *args):
        log.warn("skip entry_changed")
        return
        self.subexpr.expr = self.entryBuffer.get_text()
            
class Subtermview(object):
    """
    has .label and .exprView widgets for you to put in a table
    """
    def __init__(self, st):
        self.subterm = st
        self.graph = st.graph

        self.label = gtk.Label("sub")
        self.graph.addHandler(self.setName)
        
        sev = Subexprview(self.graph, self.subterm.uri)
        self.exprView = sev.box

    def setName(self):
        # some of this could be pushed into Submaster
        sub = self.graph.value(self.subterm.uri, L9['sub'])
        if sub is None:
            self.label.set_text("no sub (%s)" % self.subterm.uri)
            return
        label = self.graph.label(sub)
        if label is None:
            self.label.set_text("sub %s has no label" % sub)
            return
        self.label.set_text(label)

def add_one_subterm(subterm, curveset, master, show=False):
    stv = Subtermview(subterm)
    
    y = master.get_property('n-rows')
    master.attach(stv.label, 0, 1, y, y + 1, xoptions=0, yoptions=0)
    master.attach(stv.exprView, 1, 2, y, y + 1, yoptions=0)
    scrollToRowUponAdd(stv.label)  
    if show:
        master.show_all()

def scrollToRowUponAdd(widgetInRow):
    """when this table widget is ready, scroll the table so we can see it"""
    
    # this doesn't work right, yet
    return
    
    vp = widgetInRow
    while vp.get_name() != 'GtkViewport':
        log.info("walk %s", vp.get_name())
        vp = vp.get_parent()
    adj = vp.props.vadjustment

    def firstExpose(widget, event, adj, widgetInRow):
        log.info("scroll %s", adj.props.value)
        adj.props.value = adj.props.upper
        widgetInRow.disconnect(handler)
        
    handler = widgetInRow.connect('expose-event', firstExpose, adj, widgetInRow)
