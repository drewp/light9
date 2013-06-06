#!bin/python
from run_local import log
import Tkinter as tk
from light9.tkdnd import initTkdnd, dropTargetRegister
from twisted.internet import reactor, tksupport

root = tk.Tk()
initTkdnd(root.tk, "tkdnd/trunk/")
label = tk.Label(root, borderwidth=2, relief='groove', padx=10, pady=10)
label.pack()
label.config(text="drop target %s" % label._w)

frame1 = tk.Frame()
frame1.pack()

labelInner = tk.Label(frame1, borderwidth=2,
                      relief='groove', padx=10, pady=10)
labelInner.pack(side='left')
labelInner.config(text="drop target inner %s" % labelInner._w)
tk.Label(frame1, text="not a target").pack(side='left')


def onDrop(ev):
    print "onDrop", ev
def enter(ev):
    print 'enter', ev
def leave(ev):
    print 'leave', ev
dropTargetRegister(label, onDrop=onDrop, onDropEnter=enter, onDropLeave=leave,
                   hoverStyle=dict(background="yellow", relief='groove'))

dropTargetRegister(labelInner, onDrop=onDrop, onDropEnter=enter, onDropLeave=leave,
                   hoverStyle=dict(background="yellow", relief='groove'))

def prn():
    print "cont", root.winfo_containing(201,151)
b = tk.Button(root, text="coord", command=prn)
b.pack()

#tk.mainloop()
tksupport.install(root,ms=10)
reactor.run()
