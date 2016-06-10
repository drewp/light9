from light9.effect.sequencer import sendToCollector

class SubClient:
    def __init__(self):
        """assumed that your init saves self.graph"""
        pass # we may later need init code for network setup

    def get_levels_as_sub(self):
        """Subclasses must implement this method and return a Submaster
        object."""

    def send_levels(self):
        self.graph.addHandler(self._send_sub)

    def send_levels_loop(self, delay=1000):
        """This function assumes that we are an instance of a Tk object
        (or at least that we have an 'after' method)"""
        self.graph.addHandler(self.send_levels)
        self.after(delay, self.send_levels_loop, delay)

    def _send_sub(self):
        outputSettings = self.get_output_settings()
        sendToCollector('subclient', self.session, outputSettings)
