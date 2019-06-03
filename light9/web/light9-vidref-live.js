import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';


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
