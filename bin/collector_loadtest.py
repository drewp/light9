import sys
sys.path.append('bin')
from run_local import log
from light9.collector.collector_client import sendToCollector, sendToCollectorZmq
from light9.namespaces import L9, DEV
from twisted.internet import reactor
import time
import logging
log.setLevel(logging.DEBUG)


def loadTest():
    print "scheduling loadtest"
    n = 2500
    times = [None] * n
    session = "loadtest%s" % time.time()
    offset = 0
    for i in range(n):

        def send(i):
            if i % 100 == 0:
                log.info('sendToCollector %s', i)
            d = sendToCollector("http://localhost:999999/", session,
                                [[DEV["backlight1"], L9["color"], "#ffffff"],
                                 [DEV["backlight2"], L9["color"], "#ffffff"],
                                 [DEV["backlight3"], L9["color"], "#ffffff"],
                                 [DEV["backlight4"], L9["color"], "#ffffff"],
                                 [DEV["backlight5"], L9["color"], "#ffffff"],
                                 [DEV["down2"], L9["color"], "#ffffff"],
                                 [DEV["down3"], L9["color"], "#ffffff"],
                                 [DEV["down4"], L9["color"], "#ffffff"],
                                 [DEV["houseSide"], L9["level"], .8],
                                 [DEV["backlight5"], L9["uv"], 0.011]])

            def ontime(dt, i=i):
                times[i] = dt

            d.addCallback(ontime)

        reactor.callLater(offset, send, i)
        offset += .002

    def done():
        print "loadtest done"
        with open('/tmp/times', 'w') as f:
            f.write(''.join('%s\n' % t for t in times))
        reactor.stop()

    reactor.callLater(offset + .5, done)
    reactor.run()


if __name__ == '__main__':
    loadTest()
