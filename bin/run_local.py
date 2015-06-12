# allows bin/* to work without installation

# this should be turned off when the programs are installed

import sys, os, socket
sys.path.insert(0,os.path.join(os.path.dirname(sys.argv[0]),".."))

from twisted.python.failure import Failure

try:
    import Tkinter
except ImportError:
    pass
else:
    def rce(self, exc, val, tb):
        sys.stderr.write("Exception in Tkinter callback\n")
        if True:
            sys.excepthook(exc, val, tb)
        else:
            Failure(val, exc, tb).printDetailedTraceback()
    Tkinter.Tk.report_callback_exception = rce

import coloredlogs, logging, time
try:
    import faulthandler
    faulthandler.enable()
except ImportError:
    pass

progName = sys.argv[0].split('/')[-1]
log = logging.getLogger() # this has to get the root logger
log.name = progName # but we can rename it for clarity


class CSH(coloredlogs.ColoredStreamHandler):
    def render_timestamp(self, created):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created)) + (
            "%.3f" % (created % 1)).lstrip('0')

    def render_name(self, name):
        return name

log.addHandler(CSH(show_hostname=False, show_name=True))


def setTerminalTitle(s):
    if os.environ.get('TERM', '') in ['xterm', 'rxvt']:
        print "\033]0;%s\007" % s # not escaped/protected correctly

if 'listsongs' not in sys.argv[0] and 'homepageConfig' not in sys.argv[0]:
    setTerminalTitle('[%s] %s' % (socket.gethostname(), ' '.join(sys.argv)))

# see http://www.youtube.com/watch?v=3cIOT9kM--g for commands that make
# profiles and set background images
