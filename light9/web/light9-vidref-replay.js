import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import debug from '/lib/debug/debug-build-es6.js';
import _ from '/lib/underscore/underscore-min-es6.js';

const log = debug('replay');

class Light9VidrefReplay extends LitElement {
    
    static get properties() {
        return {
            uri: { type: String },
            videoUrl: { type: String },
            songToVideo: { type: Object },
            videoTime: { type: Number },
        };
    }

    setVideoTimeFromSongTime(songTime) {
        if (!this.songToVideo || !this.outVideo) {
            return;
        }
        const i = _.sortedIndex(this.songToVideo, [songTime],
                                (row) => { return row[0]; });
        this.videoTime = this.songToVideo[Math.max(0, i - 1)][1];
        this.outVideo.currentTime = this.videoTime;
    }

    firstUpdated() {
        this.outVideo = this.shadowRoot.querySelector('#replay');
    }

    onDelete() {
        const u = new URL(window.location.href);
        u.pathname = '/vidref/clips'
        u.searchParams.set('uri', this.uri);
        fetch(u.toString(), {method: 'DELETE'}).then((resp) => {
            let event = new CustomEvent('clips-changed', {detail: {}});
            this.dispatchEvent(event);
        });
    }

    static get styles() {
        return css`
        :host {
            border: 2px solid #46a79f;
            display: inline-block;
        }
        `;
    }
    
    render() {
        return html`
<div>
  <div><video id="replay" src="${this.videoUrl}"></video></div>
  <div>take is ${this.uri} (${Object.keys(this.songToVideo).length} frames)</div>
  <!-- a little canvas showing what coverage we have -->
  <div>video time is ${this.videoTime}</div>
  <button @click="${this.onDelete}">Delete</button>
</div>
`;

    }
}
customElements.define('light9-vidref-replay', Light9VidrefReplay);
