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

class FractionTimeFilter(logging.Filter):
    def filter(self, record):
        record.fractionTime = (
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created)) +
            ("%.3f" % (record.created % 1)).lstrip('0'))
        # Don't filter the record.
        return 1

coloredlogs.install(
    level='DEBUG',
    fmt='%(fractionTime)s %(name)s[%(process)d] %(levelname)s %(message)s')
logging.getLogger().handlers[0].addFilter(FractionTimeFilter())


def setTerminalTitle(s):
    if os.environ.get('TERM', '') in ['xterm', 'rxvt', 'rxvt-unicode-256color']:
        print "\033]0;%s\007" % s # not escaped/protected correctly

if 'listsongs' not in sys.argv[0] and 'homepageConfig' not in sys.argv[0]:
    setTerminalTitle('[%s] %s' % (socket.gethostname(), ' '.join(sys.argv).replace('bin/', '')))

# see http://www.youtube.com/watch?v=3cIOT9kM--g for commands that make
# profiles and set background images
