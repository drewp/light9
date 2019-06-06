/*
  url is now relative to the window location. Note that nginx may drop
  the connection after 60sec of inactivity.
*/

class ReconnectingWebsocket {
    
    constructor(url, onMessage) {
        this.onMessage = onMessage;
        this.ws = null;
        this.connectTimer = null
        this.pong = 0;
        
        this.fullUrl = (
            "ws://"
                + window.location.host
                + window.location.pathname
                + (window.location.pathname.match(/\/$/) ? "" : "/")
                + url);
        this.connect();
    }
    setStatus(txt) {
        const docStatus = document.querySelector('#status')
        if (docStatus) {
            docStatus.innerText = txt;
        }
    }
    connect() {
        this.reconnect = true;
        this.ws = new WebSocket(this.fullUrl);
        
        this.ws.onopen = () => { this.setStatus("connected"); };
        this.ws.onerror = (e) => { this.setStatus("error: "+e); };
        this.ws.onclose = () => {
            this.pong = 1 - this.pong;
            this.setStatus("disconnected (retrying "+(this.pong ? "😼":"😺")+")");
            this.ws = null;

            this.connectTimer = setTimeout(() => {
                this.connectTimer = null;
                requestAnimationFrame(() => {
                    if (this.reconnect) {
                        this.connect();
                    }
                });
            }, 2000);
        };
        this.ws.onmessage = (evt) => {
            this.onMessage(JSON.parse(evt.data));
        };
    }
    disconnect() {
        this.reconnect = false;
        this.ws.close();
    }
}



function reconnectingWebSocket(url, onMessage) {
    return new ReconnectingWebsocket(url, onMessage);
}
