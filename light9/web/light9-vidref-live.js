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

    static get styles() {
        return css`
        :host {
            border: 2px solid #46a79f;
            display: inline-block;
        }
        `;
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
    
    render() {
        return html`
<div>
  <label><input type="checkbox" id="enabled" ?checked="${this.enabled}" @change="${this.onEnabled}">Show live</label>
  <div id="liveWidget"><img id="live" ></div>
</div>
`;

    }
}
customElements.define('light9-vidref-live', Light9VidrefLive);
