import gtk
from rdflib import URIRef

class Local(object):
    """placeholder for the local uri that EditChoice does not
    manage. Set resourceObservable to Local to indicate that you're
    unlinked"""

class EditChoice(gtk.HBox):
    """
    this is a gtk port of editchoice.EditChoice
    """
    def __init__(self, graph, resourceObservable, label="Editing:"):
        """
        getResource is called to get the URI of the currently
        """
        self.graph = graph

        # the outer box should have a distinctive border so it's more
        # obviously a special drop target
        gtk.HBox.__init__(self)
        self.pack_start(gtk.Label(label), expand=False)

        # this is just a label, but it should look like a physical
        # 'thing' (and gtk labels don't work as drag sources)
        self.currentLink = gtk.Button("http://bar")

        self.pack_start(self.currentLink)

        self.unlinkButton = gtk.Button(label="Unlink")
        self.pack_start(self.unlinkButton, expand=False)
        self.unlinkButton.connect("clicked", self.onUnlink)
        
        self.show_all()

        self.resourceObservable = resourceObservable
        resourceObservable.subscribe(self.uriChanged)

        self.makeDragSource()
        self.makeDropTarget()
         
    def makeDropTarget(self):
        def ddr(widget, drag_context, x, y, selection_data, info, timestamp):
            if selection_data.type != 'text/uri-list':
                raise ValueError("unknown DnD selection type %r" %
                                 selection_data.type)
            self.resourceObservable(URIRef(selection_data.data.strip()))
        
        self.currentLink.drag_dest_set(flags=gtk.DEST_DEFAULT_ALL,
                            targets=[('text/uri-list', 0, 0)],
                            actions=gtk.gdk.ACTION_LINK  | gtk.gdk.ACTION_COPY)
        self.currentLink.connect("drag_data_received", ddr)
                
    def makeDragSource(self):
        self.currentLink.drag_source_set(
            start_button_mask=gtk.gdk.BUTTON1_MASK,
            targets=[('text/uri-list', 0, 0)],
            actions=gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)

        def source_drag_data_get(btn, context, selection_data, info, time):
            selection_data.set(selection_data.target, 8,
                               self.resourceObservable())

        self.currentLink.connect("drag_data_get", source_drag_data_get)

                
    def uriChanged(self, newUri):
        # if this resource had a type icon or a thumbnail, those would be
        # cool to show in here too
        if newUri is Local:
            self.currentLink.set_label("(local)")
            self.currentLink.drag_source_unset()
        else:
            self.graph.addHandler(self.updateLabel)
            self.makeDragSource()
        self.unlinkButton.set_sensitive(newUri is not Local)

    def updateLabel(self):
        uri = self.resourceObservable()
        label = self.graph.label(uri)
        self.currentLink.set_label(label or uri or "")

    def onUnlink(self, *args):
        self.resourceObservable(Local)
