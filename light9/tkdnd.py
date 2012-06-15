from glob import glob
from os.path import join, basename

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
    widget.tk.call('tkdnd::drag_source', 'register', widget._w)

    # with normal Tkinter bind(), the result of your handler isn't
    # actually returned so the drag doesn't get launched. This is a
    # corrected version of what bind() does when you pass a function,
    # but I don't block my tuple from getting returned (as a tcl list)
    funcId = widget._register(lambda: (action, datatype, data),
                              widget._substitute,
                              1 # needscleanup
                              )
    widget.bind("<<DragInitCmd>>", funcId)
