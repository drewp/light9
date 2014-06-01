from gi.repository import Gtk
from gi.repository import Gdk
from rdflib import URIRef

class Local(object):
    """placeholder for the local uri that EditChoice does not
    manage. Set resourceObservable to Local to indicate that you're
    unlinked"""

class EditChoice(Gtk.HBox):
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
        Gtk.HBox.__init__(self)
        self.pack_start(Gtk.Label(label),
                        False, True, 0) #expand, fill, pad

        # this is just a label, but it should look like a physical
        # 'thing' (and gtk labels don't work as drag sources)
        self.currentLink = Gtk.Button("http://bar")

        self.pack_start(self.currentLink,
                        True, True, 0) #expand, fill, pad


        self.unlinkButton = Gtk.Button(label="Unlink")
        self.pack_start(self.unlinkButton,
                        False, True, 0) #expand, fill pad

        self.unlinkButton.connect("clicked", self.onUnlink)
        
        self.show_all()

        self.resourceObservable = resourceObservable
        resourceObservable.subscribe(self.uriChanged)

        self.makeDragSource()
        self.makeDropTarget()
         
    def makeDropTarget(self):
        def ddr(widget, drag_context, x, y, selection_data, info, timestamp):
            if selection_data.get_data_type().name() != 'text/uri-list':
                raise ValueError("unknown DnD selection type %r" %
                                 selection_data.get_data_type())
            self.resourceObservable(URIRef(selection_data.get_data().strip()))
        
        self.currentLink.drag_dest_set(
            flags=Gtk.DestDefaults.ALL,
            targets=[Gtk.TargetEntry.new('text/uri-list', 0, 0)],
            actions=Gdk.DragAction.LINK  | Gdk.DragAction.COPY)
        self.currentLink.connect("drag_data_received", ddr)
                
    def makeDragSource(self):
        self.currentLink.drag_source_set(
            start_button_mask=Gdk.ModifierType.BUTTON1_MASK,
            targets=[Gtk.TargetEntry.new(target='text/uri-list',
                                         flags=0, info=0)],
            actions=Gdk.DragAction.LINK  | Gdk.DragAction.COPY)

        def source_drag_data_get(btn, context, selection_data, info, time):
            selection_data.set_uris([self.resourceObservable()])

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
