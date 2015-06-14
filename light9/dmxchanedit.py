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
from rdflib import RDF, Literal
import math, logging
from decimal import Decimal
from light9.namespaces import L9
log = logging.getLogger('dmxchanedit')
stdfont = ('Arial', 7)

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

    and the level is like this:

       ?editor :currentSub ?sub .
       ?sub :lightLevel [:channel ?ch; :level ?level] .

    levels come in with self.setTo and go out by the onLevelChange
    callback. This object does not use the graph for level values,
    which I'm doing for what I think is efficiency. Unclear why I
    didn't use Observable for that API.
    """
    def __init__(self, parent, graph, channelUri, onLevelChange):
        tk.Frame.__init__(self,parent, height=20)
        self.graph = graph
        self.onLevelChange = onLevelChange
        self.uri = channelUri
        self.currentLevel = 0 # the level we're displaying, 0..1

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
        self.desc_lab=tk.Label(self,
                               width=14,
                               font=stdfont,
                               anchor='w',
                               padx=0, pady=0, bd=0,
                 height=1, bg='black', fg='white')
        self.graph.addHandler(self.updateLabel)
        self.desc_lab.pack(side='left')

        # current level of channel, shows intensity with color
        self.level_lab = tk.Label(self, width=3, bg='lightBlue',
                                  anchor='e', font=stdfont,
                                  padx=1, pady=0, bd=0, height=1)
        self.level_lab.pack(side='left')

        self.setupmousebindings()

    def updateLabel(self):
         self.desc_lab.config(text=self.graph.label(self.uri))

    def setupmousebindings(self):
        def b1down(ev):
            self.desc_lab.config(bg='cyan')
            self._start_y=ev.y
            self._start_lev=self.currentLevel
        def b1motion(ev):
            delta=self._start_y-ev.y
            self.setlevel(max(0, min(1, self._start_lev+delta*.005)))
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
        """UI received a level change, which we put in the graph"""
        self.onLevelChange(self.uri, newlev)

    def setTo(self, newLevel):
        """levelbox saw a change in the graph"""
        self.currentLevel = min(1, max(0, newLevel))
        newLevel = "%d" % (self.currentLevel * 100)
        olddisplay=self.level_lab.cget('text')
        if newLevel != olddisplay:
            self.level_lab.config(text=newLevel)
            self.colorlabel()


class Levelbox(tk.Frame):
    """
    this also watches all the levels in the sub and sets the boxes when they change
    """
    def __init__(self, parent, graph, currentSub):
        """
        currentSub is an Observable(PersistentSubmaster)
        """
        tk.Frame.__init__(self,parent)

        self.currentSub = currentSub
        self.graph = graph
        graph.addHandler(self.updateChannels)

        self.currentSub.subscribe(lambda _: graph.addHandler(self.updateLevelValues))

    def updateChannels(self):
        """(re)make Onelevel boxes for the defined channels"""

        [ch.destroy() for ch in self.winfo_children()]
        self.levelFromUri = {} # channel : OneLevel

        chans = list(self.graph.subjects(RDF.type, L9.Channel))
        chans.sort(key=lambda c: int(self.graph.value(c, L9.output).rsplit('/c')[-1]))
        cols = 2
        rows = int(math.ceil(len(chans) / cols))

        def make_frame(parent):
             f = tk.Frame(parent, bd=0, bg='black')
             f.pack(side='left')
             return f

        columnFrames = [make_frame(self) for x in range(cols)]

        for i, channel in enumerate(chans): # sort?
            # frame for this channel
            f = Onelevel(columnFrames[i // rows], self.graph, channel,
                         self.onLevelChange)

            self.levelFromUri[channel] = f
            f.pack(side='top')

    def updateLevelValues(self):
        """set UI level from graph"""
        submaster = self.currentSub()
        if submaster is None:
            return
        sub = submaster.uri
        if sub is None:
            raise ValueError("currentSub is %r" % submaster)

        remaining = set(self.levelFromUri.keys())
        for ll in self.graph.objects(sub, L9['lightLevel']):
            chan = self.graph.value(ll, L9['channel'])
            try:
                 lev = self.graph.value(ll, L9['level']).toPython()
            except AttributeError as e:
                 log.error('on lightlevel %r:', ll)
                 log.exception(e)
                 continue
            if isinstance(lev, Decimal):
                 lev = float(lev)
            assert isinstance(lev, (int, long, float)), repr(lev)
            try:
                 self.levelFromUri[chan].setTo(lev)
                 remaining.remove(chan)
            except KeyError as e:
                 log.exception(e)
        for channel in remaining:
            self.levelFromUri[channel].setTo(0)

    def onLevelChange(self, chan, newLevel):
        """UI received a change which we put in the graph"""
        if self.currentSub() is None:
            raise ValueError("no currentSub in Levelbox")
        self.currentSub().editLevel(chan, newLevel)

