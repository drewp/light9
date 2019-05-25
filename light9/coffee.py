from cycloneerr import PrettyErrorHandler
import cyclone.web
import subprocess


class StaticCoffee(PrettyErrorHandler, cyclone.web.RequestHandler):
    """
    e.g.

            (r'/effect\.js', StaticCoffee, {
                'src': 'light9/effecteval/effect.coffee'
            }),
    """ # noqa

    def initialize(self, src):
        super(StaticCoffee, self).initialize()
        self.src = src

    def get(self):
        self.set_header('Content-Type', 'application/javascript')
        self.write(
            subprocess.check_output(
                ['/usr/bin/coffee', '--compile', '--print', self.src]))
