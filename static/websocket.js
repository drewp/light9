function reconnectingWebSocket(url, onMessage) {
    var pong = 0;
    function connect() {
        var ws = new WebSocket(url);
        
        ws.onopen = function() {   $("#status").text("connected"); };
        ws.onerror = function(e) { $("#status").text("error: "+e); };
        ws.onclose = function() {  
            pong = 1 - pong;
            $("#status").text("disconnected (retrying "+(pong ? "😼":"😺")+")"); 
            // this should be under a requestAnimationFrame to
            // save resources
            setTimeout(connect, 2000);
        };
        ws.onmessage = function (evt) {
            onMessage(JSON.parse(evt.data));
        };
    }
    connect();
}