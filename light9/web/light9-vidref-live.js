import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import { rounding }  from '/node_modules/significant-rounding/index.js';
import './light9-vidref-replay.js';

import debug from '/lib/debug/debug-build-es6.js';
const log = debug('live');

class Light9VidrefLive extends LitElement {
    
    static get properties() {
        return {
            description: { type: String },
            enabled: { type: Boolean }
        };
    }
    
    constructor() {
        super();
        this.live = null;
    }
    
    onEnabled() {
        if (this.shadowRoot.querySelector('#enabled').checked) {
            
            this.live = reconnectingWebSocket(
                'live', (msg) => {
                    this.shadowRoot.querySelector('#live').src = 'data:image/jpeg;base64,' + msg.jpeg;
                    this.description = msg.description;
                });
            this.shadowRoot.querySelector('#liveWidget').style.display = 'block';
        } else {
            if (this.live) {
                this.live.disconnect();
                this.live = null;
                this.shadowRoot.querySelector('#liveWidget').style.display = 'none';
            }
        }
    }

    disconnectedCallback() {
        log('bye');
        //close socket
        
    }

    static get styles() {
        return css`
        :host {
            display: inline-block;
        }
#live {
border: 4px solid orange;
}
        `;
    }
    
    render() {
        return html`
  <label><input type="checkbox" id="enabled" ?checked="${this.enabled}" @change="${this.onEnabled}">Show live</label>
  <div id="liveWidget" style="display: none"><img id="live" ></div>
`;

    }
}
customElements.define('light9-vidref-live', Light9VidrefLive);
