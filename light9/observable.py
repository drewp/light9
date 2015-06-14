import logging
log = logging.getLogger('observable')

class _NoNewVal(object):
    pass

class Observable(object):
    """
    like knockout's observable. Hopefully this can be replaced by a
    better python one

    compare with:
    http://knockoutjs.com/documentation/observables.html
    https://github.com/drpancake/python-observable/blob/master/observable/observable.py
    """
    def __init__(self, val):
        self.val = val
        self.subscribers = set()

    def __call__(self, newVal=_NoNewVal):
        if newVal is _NoNewVal:
            return self.val
        if newVal == self.val:
            log.debug("%r unchanged from %r", newVal, self.val)
            return
        self.val = newVal
        for s in self.subscribers:
            s(newVal)

    def subscribe(self, cb, callNow=True):
        """cb is called with new values, and also right now with the
        current value unless you opt out"""
        self.subscribers.add(cb)
        if callNow:
            cb(self.val)
