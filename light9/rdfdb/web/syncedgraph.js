function SyncedGraph(label) {
    /*
      like python SyncedGraph but talks over a websocket to
      rdfdb. This one has an API more conducive to reading and
      querying.

      light9/web/graph.coffee is the newer attempt
    */
    var self = this;

    

    self.patch = function (p) {
        throw;
    }
    self.nodesWithSubstring = function (subString) {

    }
    self.quads = function (s, p, o, c) {
        // any args can be null for wildcard
    }


    function onMessage(d) {
        $('#out').append($('<div>').text(JSON.stringify(d)));
    }
    
    reconnectingWebSocket("liveSyncedGraph", onMessage);
}
