# allows bin/* to work without installation

# this should be turned off when the programs are installed

import sys,os
sys.path.insert(0,os.path.join(os.path.dirname(sys.argv[0]),".."))

from twisted.python.failure import Failure

import Tkinter
def rce(self, exc, val, tb):
    sys.stderr.write("Exception in Tkinter callback\n")
    if True:
        sys.excepthook(exc, val, tb)
    else:
        Failure(val, exc, tb).printDetailedTraceback()
Tkinter.Tk.report_callback_exception = rce

import coloredlogs, logging, time
log = logging.getLogger()

class CSH(coloredlogs.ColoredStreamHandler):
    def render_timestamp(self, created):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created)) + (
            "%.3f" % (created % 1)).lstrip('0')

    def render_name(self, name):
        return name

log.addHandler(CSH(show_hostname=False, show_name=True))


def setTerminalTitle(s):
    if os.environ.get('TERM', '') in ['xterm']:
        print "\033]0;%s\007" % s # not escaped/protected correctly

setTerminalTitle(sys.argv[0])
