from typing import List

import cyclone.web

import greplin.scales.twistedweb, greplin.scales.formats, greplin.scales.util
from greplin import scales


# Like scales.twistedweb.StatsResource, but modified for cyclone. May
# be missing features.
class StatsForCyclone(cyclone.web.RequestHandler):

    def get(self):
        parts: List[str] = []
        statDict = greplin.scales.util.lookup(scales.getStats(), parts)

        if statDict is None:
            self.set_status(404)
            self.write("Path not found.")
            return

        query = self.get_argument('query', default=None)

        if self.get_argument('format', default=None) == 'json':
            self.set_header('content-type', 'text/javascript; charset=UTF-8')
            greplin.scales.formats.jsonFormat(self, statDict, query)
        elif self.get_argument('format', default=None) == 'prettyjson':
            self.set_header('content-type', 'text/javascript; charset=UTF-8')
            greplin.scales.formats.jsonFormat(self,
                                              statDict,
                                              query,
                                              pretty=True)
        else:
            greplin.scales.formats.htmlHeader(self, '/' + '/'.join(parts),
                                              'svr', query)
            greplin.scales.formats.htmlFormat(self, tuple(parts), statDict,
                                              query)
