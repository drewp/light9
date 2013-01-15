from glob import glob
from os.path import join, basename

class TkdndEvent(object):
    """
    see http://www.ellogon.org/petasis/tcltk-projects/tkdnd/tkdnd-man-page
    for details on the fields

    The longer attribute names (action instead of %A) were made up for
    this API.

    Not all attributes are visible yet, since I have not thought
    through what conversions they should receive and I don't want to
    unnecessarily change their types later.
    """
    substitutions = {
        "%A" : "action",
        "%b" : "button",
        "%D" : "data",
        "%m" : "modifiers",
        "%T" : "type",
        "%W" : "targetWindow",
        "%X" : "mouseX",
        "%Y" : "mouseY",
        }

    @classmethod
    def makeEvent(cls, *args):
        ev = cls()
        for (k, v), arg in zip(sorted(TkdndEvent.substitutions.items()), args):
            setattr(ev, v, arg)
        # it would be cool for this to decode text data according to the charset in the type
        for attr in ['button', 'mouseX', 'mouseY']:
            setattr(ev, attr, int(getattr(ev, attr)))
        return (ev,)

    tclSubstitutions = ' '.join(sorted(substitutions.keys()))

    def __repr__(self):
        return "<TkdndEvent %r>" % self.__dict__

class Hover(object):
    def __init__(self, widget, style):
        self.widget, self.style = widget, style
        self.oldStyle = {}

    def set(self, ev):
        for k, v in self.style.items():
            self.oldStyle[k] = self.widget.cget(k)
        self.widget.configure(**self.style)
        print "set with", ev
        return ev.action

    def restore(self, ev):
        print "restore", self.oldStyle
        self.widget.configure(**self.oldStyle)

def initTkdnd(tk, tkdndBuildDir):
    """
    pass the 'tk' attribute of any Tkinter object, and the top dir of
    your built tkdnd package
    """
    tk.call('source', join(tkdndBuildDir, 'library/tkdnd.tcl'))
    for dll in glob(join(tkdndBuildDir,
                         '*tkdnd*' + tk.call('info', 'sharedlibextension'))):
        tk.call('tkdnd::initialise',
                join(tkdndBuildDir, 'library'),
                join('..', basename(dll)),
                'tkdnd')

def dragSourceRegister(widget,
                       action='copy', datatype='text/uri-list', data=''):
    """
    if the 'data' param is callable, it will be called every time to
    look up the current data
    """
    widget.tk.call('tkdnd::drag_source', 'register', widget._w)

    # with normal Tkinter bind(), the result of your handler isn't
    # actually returned so the drag doesn't get launched. This is a
    # corrected version of what bind() does when you pass a function,
    # but I don't block my tuple from getting returned (as a tcl list)

    def init():
        return (action, datatype, data() if callable(data) else data)
    
    funcId = widget._register(init, 
                              widget._substitute,
                              1 # needscleanup
                              )
    widget.bind("<<DragInitCmd>>", funcId)

def dropTargetRegister(widget, typeList=None,
                       onDropEnter=None,
                       onDropPosition=None,
                       onDropLeave=None,
                       onDrop=None,
                       hoverStyle=None,
                       ):
    """
    the optional callbacks will be called with a TkdndEvent
    argument.

    onDropEnter, onDropPosition, and onDrop are supposed to return an
    action (perhaps the value in event.action). The return value seems
    to have no effect, but it might just be that errors are getting
    silenced.

    Passing hoverStyle sets onDropEnter to call
    widget.configure(**hoverStyle) and onDropLeave to restore the
    widget's style. onDrop is also wrapped to do a restore.
    """

    if hoverStyle is not None:
        hover = Hover(widget, hoverStyle)
        def wrappedDrop(ev):
            hover.restore(ev)
            if onDrop:
                return onDrop(ev)
        return dropTargetRegister(widget, typeList=typeList,
                                  onDropEnter=hover.set,
                                  onDropLeave=hover.restore,
                                  onDropPosition=onDropPosition,
                                  onDrop=wrappedDrop)

    if typeList is None:
        typeList = ['*']
    widget.tk.call(*(['tkdnd::drop_target', 'register', widget._w]+typeList))

    for sequence, handler in [
        ('<<DropEnter>>', onDropEnter),
        ('<<DropPosition>>', onDropPosition),
        ('<<DropLeave>>', onDropLeave),
        ('<<Drop>>', onDrop),
        ]:
        if not handler:
            continue
        func = widget._register(handler, subst=TkdndEvent.makeEvent, needcleanup=1)
        widget.bind(sequence, func + " " + TkdndEvent.tclSubstitutions)


