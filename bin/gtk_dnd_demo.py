#!bin/python
import run_local
import gtk
import sys
sys.path.append(".")
from rdflib import URIRef
from light9 import networking
from light9.editchoicegtk import EditChoice, Local
from light9.observable import Observable
from rdfdb.syncedgraph import SyncedGraph

win = gtk.Window()

graph = SyncedGraph(networking.rdfdb.url, "gtkdnddemo")

r1 = URIRef("http://example.com/interestingThing")
v = Observable(r1)
win.add(EditChoice(graph, v))
win.show_all()
gtk.main()
