#!bin/python
from run_local import log
import colorsys, time, logging
from light9 import dmxclient
from twisted.internet import reactor, task

log.setLevel(logging.INFO)
firstDmxChannel = 10

def step():
    hue = (time.time() * .2) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
    chans = [r, g, b]
    log.info(chans)
    dmxclient.outputlevels([0] * (firstDmxChannel - 1) + chans, twisted=True)


task.LoopingCall(step).start(.05)
reactor.run()
