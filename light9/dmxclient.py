""" module for clients to use for easy talking to the dmx
server. sending levels is now a simple call to
dmxclient.outputlevels(..)

client id is formed from sys.argv[0] and the PID.  """

import xmlrpclib, os, sys, socket, time, logging
from twisted.internet import defer
from txzmq import ZmqEndpoint, ZmqFactory, ZmqPushConnection
import json

from light9 import networking
_dmx=None
log = logging.getLogger('dmxclient')

procname = os.path.basename(sys.argv[0])
procname = procname.replace('.py', '')
_id = "%s-%s-%s" % (procname, socket.gethostname(), os.getpid())

class TwistedZmqClient(object):
    def __init__(self, service):
        zf = ZmqFactory()
        e = ZmqEndpoint('connect', 'tcp://%s:%s' % (service.host, service.port))
        self.conn = ZmqPushConnection(zf, e)
        
    def send(self, clientid, levellist):
        self.conn.push(json.dumps({'clientid': clientid, 'levellist': levellist}))

def outputlevels(levellist,twisted=0,clientid=_id):
    """present a list of dmx channel levels, each scaled from
    0..1. list can be any length- it will apply to the first len() dmx
    channels.

    if the server is not found, outputlevels will block for a
    second."""

    global _dmx, _id

    if _dmx is None:
        url = networking.dmxServer.url
        if not twisted:
            _dmx = xmlrpclib.Server(url)
        else:
            _dmx = TwistedZmqClient(networking.dmxServerZmq)

    if not twisted:
        try:
            _dmx.outputlevels(clientid, levellist)
        except socket.error, e:
            log.error("dmx server error %s, waiting" % e)
            time.sleep(1)
        except xmlrpclib.Fault,e:
            log.error("outputlevels had xml fault: %s" % e)
            time.sleep(1)
    else:
        _dmx.send(clientid, levellist)
        return defer.succeed(None)
    
dummy = os.getenv('DMXDUMMY')
if dummy:
    print "dmxclient: DMX is in dummy mode."
    def outputlevels(*args, **kw):
        pass
