"""

widget to show all dmx channel levels and allow editing. levels might
not actually match what dmxserver is outputting.

proposal for new focus and edit system:
- rows can be selected
- the chan number or label can be used to select rows. dragging over rows brings all of them into or out of the current selection
- numbers drag up and down (like today)
- if you drag a number in a selected row, all the selected numbers change
- if you start dragging a number in an unselected row, your row becomes the new selection and then the edit works


proposal for new attribute system:
- we always want to plan some attributes for each light: where to center; what stage to cover; what color gel to apply; whether the light is burned out
- we have to stop packing these into the names. Names should be like 'b33' or 'blue3' or just '44'. maybe 'blacklight'.

"""
from __future__ import nested_scopes,division
import Tkinter as tk
from rdflib import RDF
from light9.namespaces import L9
import louie as dispatcher

stdfont = ('Arial', 9)

def gradient(lev, low=(80,80,180), high=(255,55,50)):
     out = [int(l+lev*(h-l)) for h,l in zip(high,low)]
     col="#%02X%02X%02X" % tuple(out)
     return col

class Onelevel(tk.Frame):
    """a name/level pair

    source data is like this:
        ch:b11-c     a :Channel;
         :output dmx:c54;
         rdfs:label "b11-c" .
    """
    def __init__(self, parent, graph, channelUri):
        tk.Frame.__init__(self,parent, height=20)
        self.graph = graph
        self.uri = channelUri
        self.currentlevel = 0 # the level we're displaying, 0..1

        # no statement yet
        self.channelnum = int(
             self.graph.value(self.uri, L9['output']).rsplit('/c')[-1])

        # 3 widgets, left-to-right:

        # channel number -- will turn yellow when being altered
        self.num_lab = tk.Label(self, text=str(self.channelnum),
                                width=3, bg='grey40', 
                                fg='white',
                                font=stdfont,
                                padx=0, pady=0, bd=0, height=1)
        self.num_lab.pack(side='left')

        # text description of channel
        self.desc_lab=tk.Label(self, text=self.graph.label(self.uri),
                               width=14,
                               font=stdfont,
                               anchor='w',
                               padx=0, pady=0, bd=0, 
                 height=1, bg='black', fg='white')
        self.desc_lab.pack(side='left')

        # current level of channel, shows intensity with color
        self.level_lab = tk.Label(self, width=3, bg='lightBlue',
                                  anchor='e', font=stdfont,
                                  padx=1, pady=0, bd=0, height=1)
        self.level_lab.pack(side='left')

        self.setlevel(0)
        self.setupmousebindings()
        
    def setupmousebindings(self):
        def b1down(ev):
            self.desc_lab.config(bg='cyan')
            self._start_y=ev.y
            self._start_lev=self.currentlevel
        def b1motion(ev):
            delta=self._start_y-ev.y
            self.setlevel(self._start_lev+delta*.005)
        def b1up(ev):
            self.desc_lab.config(bg='black')
        def b3up(ev):
            self.setlevel(0.0)
        def b3down(ev):
            self.setlevel(1.0)
        def b2down(ev): # same thing for now
            self.setlevel(1.0)

        # make the buttons work in the child windows
        for w in self.winfo_children():
            for e,func in (('<ButtonPress-1>',b1down),
                           ('<B1-Motion>',b1motion),
                           ('<ButtonRelease-1>',b1up),
                           ('<ButtonPress-2>', b2down),
                           ('<ButtonRelease-3>', b3up),
                           ('<ButtonPress-3>', b3down)):

                w.bind(e,func)
        
    def colorlabel(self):
        """color the level label based on its own text (which is 0..100)"""
        txt=self.level_lab['text'] or "0"
        lev=float(txt)/100
        self.level_lab.config(bg=gradient(lev))

    def setlevel(self, newlev):
        """the main program is telling us to change our
        display. newlev is 0..1"""
        self.currentlevel = min(1, max(0, newlev))
        newlev = "%d" % (self.currentlevel * 100)
        olddisplay=self.level_lab.cget('text')
        if newlev!=olddisplay:
            self.level_lab.config(text=newlev)
            self.colorlabel()
        dispatcher.send("levelchanged", channel=self.uri, newlevel=newlev)

class Levelbox(tk.Frame):
    def __init__(self, parent, graph):
        tk.Frame.__init__(self,parent)

        self.graph = graph
        graph.addHandler(self.updateChannels)

    def updateChannels(self):
        """(re)make Onelevel boxes for the defined channels"""

        [ch.destroy() for ch in self.winfo_children()]
        self.levels = [] # Onelevel objects

        chans = list(self.graph.subjects(RDF.type, L9.Channel))
        chans.sort(key=lambda c: int(self.graph.value(c, L9.output).rsplit('/c')[-1]))
        cols = 2
        rows = len(chans) // cols

        def make_frame(parent):
             f = tk.Frame(parent, bd=0, bg='black')
             f.pack(side='left')
             return f
        
        columnFrames = [make_frame(self) for x in range(cols)]

        for i, channel in enumerate(chans): # sort?
            # frame for this channel
            f = Onelevel(columnFrames[i // rows], self.graph, channel)

            self.levels.append(f)
            f.pack(side='top')
        #dispatcher.connect(setalevel,"setlevel")

    def setlevels(self,newlevels):
        """sets levels to the new list of dmx levels (0..1). list can
        be any length"""
        for l,newlev in zip(self.levels,newlevels):
            l.setlevel(newlev)
