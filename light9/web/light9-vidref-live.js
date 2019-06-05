import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import debug from '/lib/debug/debug-build-es6.js';
debug.enable('*');
const log = debug('live');
log('hi it is live')

class Light9VidrefLive extends LitElement {
    
    static get properties() {
        return {
            description: { type: String }
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

    firstUpdated() {
        const ws = reconnectingWebSocket('live', (msg) => {
            this.shadowRoot.querySelector('#live').src = 'data:image/jpeg;base64,' + msg.jpeg;
            this.description = msg.description;
        });
        
    }

    disconnectedCallback() {
        log('bye');
        
    }
    
    render() {
        return html`
<div>
<div><img id="live" ></div>
<div>${this.description}</div>
</div>
`;

    }
}
customElements.define('light9-vidref-live', Light9VidrefLive);
