import Tkinter as tk
from rdflib import URIRef
from light9.tkdnd import dragSourceRegister, dropTargetRegister

class Local(object):
    """placeholder for the local uri that EditChoice does not
    manage. Set resourceObservable to Local to indicate that you're
    unlinked"""

class EditChoice(object):
    """
    Observable <-> linker UI

    widget for tying some UI to a shared resource for editing, or
    unlinking it (which means associating it with a local resource
    that's not named or shared). This object does not own the choice
    of resource; the caller does.

    UI actions:
    - drag a uri on here to make it the one we're editing

    - button to clear the currentSub (putting it back to
      sessionLocalSub, and also resetting sessionLocalSub to be empty
      again)

    - drag the sub uri off of here to send it to another receiver,
      but, if we're in local mode, the local sub should not be so
      easily addressable. Maybe you just can't drag it off.


    Todo:

    - filter by type so you can't drag a curve onto a subcomposer

    - 'save new' : make a new sub: transfers the current data (from a shared sub or
      from the local one) to the new sub. If you're on a local sub,
      the new sub is named automatically, ideally something brief,
      pretty distinct, readable, and based on the lights that are
      on. If you're on a named sub, the new one starts with a
      'namedsub 2' style name. The uri can also be with a '2' suffix,
      although maybe that will be stupid. If you change the name
      before anyone knows about this uri, we could update the current
      sub's uri to a slug of the new label.

    - rename this sub: not available if you're on a local sub. Sets
      the label of a named sub. Might update the uri of the named sub
      if it's new enough that no one else would have that uri. Not
      sure where we measure that 'new enough' value. Maybe track if
      the sub has 'never been dragged out of this subcomposer
      session'? But subs will also show up in other viewers and
      finders.

    - list of recent resources that this choice was set to
    """
    def __init__(self, parent, graph, resourceObservable, label="Editing:"):
        """
        getResource is called to get the URI of the currently
        """
        self.graph = graph
        self.frame = tk.Frame(parent, relief='raised', border=2)
        self.frame.pack(side='top')
        tk.Label(self.frame, text=label).pack(side='left')
        self.currentLinkFrame = tk.Frame(self.frame)
        self.currentLinkFrame.pack(side='left')

        self.subIcon = tk.Label(self.currentLinkFrame, text="...",
                                borderwidth=2, relief='raised',
                                padx=10, pady=10)
        self.subIcon.pack()

        self.resourceObservable = resourceObservable
        resourceObservable.subscribe(self.uriChanged)

        # when the value is local, this should stop being a drag source
        dragSourceRegister(self.subIcon, 'copy', 'text/uri-list',
                           self.resourceObservable)
        def onEv(ev):
            self.resourceObservable(URIRef(ev.data))
            return "link"
        self.onEv = onEv

        b=tk.Button(self.frame, text="Unlink", command=self.switchToLocalSub)
        b.pack(side='left')

        # it would be nice if I didn't receive my own drags here, and
        # if the hover display wasn't per widget
        for target in ([self.frame, self.currentLinkFrame] +
                       self.frame.winfo_children() +
                       self.currentLinkFrame.winfo_children()):
            dropTargetRegister(target, typeList=["*"], onDrop=onEv,
                               hoverStyle=dict(background="#555500"))

    def uriChanged(self, newUri):
        # if this resource had a type icon or a thumbnail, those would be
        # cool to show in here too
        if newUri is Local:
            self.subIcon.config(text="(local)")
        else:
            self.graph.addHandler(self.updateLabel)

    def updateLabel(self):
        uri = self.resourceObservable()
        print "get label", repr(uri)
        label = self.graph.label(uri)
        self.subIcon.config(text=label or uri)

    def switchToLocalSub(self):
        self.resourceObservable(Local)

