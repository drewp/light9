import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import debug from '/lib/debug/debug-build-es6.js';
import _ from '/lib/underscore/underscore-min-es6.js';
import { rounding }  from '/node_modules/significant-rounding/index.js';

const log = debug('replay');

class Light9VidrefReplay extends LitElement {
    
    static get properties() {
        return {
            uri: { type: String },
            videoUrl: { type: String },
            songToVideo: { type: Object },
            videoTime: { type: Number },
            outVideoCurrentTime: { type: Number },
            timeErr: { type: Number },
            playRate: { type: Number },
            size: { type: String, attribute: true }
        };
    }
    estimateRate() {
        const n = this.songToVideo.length;
        const x0 = Math.round(n * .3);
        const x1 = Math.round(n * .6);
        const pt0 = this.songToVideo[x0];
        const pt1 = this.songToVideo[x1];
        return (pt1[1] - pt0[1]) / (pt1[0] - pt0[0]);
    }
    setVideoTimeFromSongTime(songTime, isPlaying) {
        if (!this.songToVideo || !this.outVideo || this.outVideo.readyState < 1) {
            return;
        }
        const i = _.sortedIndex(this.songToVideo, [songTime],
                                (row) => { return row[0]; });
        this.videoTime = this.songToVideo[Math.max(0, i - 1)][1];

        this.outVideoCurrentTime = this.outVideo.currentTime;
        
        if (isPlaying) {
            if (this.outVideo.paused) {
                this.outVideo.play();
                this.setRate(this.estimateRate());
            }
            const err = this.outVideo.currentTime - this.videoTime;
            this.timeErr = err;

            if (Math.abs(err) > window.thresh) {
                this.outVideo.currentTime = this.videoTime;
                const p = window.p;
                if (err > 0) {
                    this.setRate(this.playRate - err * p);
                } else {
                    this.setRate(this.playRate - err * p);
                }
            }
        } else {
            this.outVideo.pause();
            this.outVideoCurrentTime = this.outVideo.currentTime = this.videoTime;
            this.timeErr = 0;
        }
    }
    setRate(r) {
        this.playRate = Math.max(.1, Math.min(4, r));
        this.outVideo.playbackRate = this.playRate;
    }

    firstUpdated() {
        this.outVideo = this.shadowRoot.querySelector('#replay');
        this.playRate = this.outVideo.playbackRate = 1.0;
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
            margin: 5px;
            border: 2px solid #46a79f;
            display: flex;
            flex-direction: column;
        }
        div {
            padding: 5px;
        }
        .num {
            display: inline-block;
            width: 4em;
            color: #29ffa0;
        }
        a {
            color: rgb(97, 97, 255);
        }
        video.size-small {
          width: 60%;
        }
        `;
    }
    
    render() {
        let details = '';
        if (this.size != 'small') {
            details = html`  <div>
    take is <a href="${this.uri}">${this.uri}</a> 
    (${Object.keys(this.songToVideo).length} frames)
    <button @click="${this.onDelete}">Delete</button>
  </div>
  <!-- here, put a little canvas showing what coverage we have with the 
       actual/goal time cursors -->
  <div>
    video time should be <span class="num">${this.videoTime} </span>
    actual = <span class="num">${rounding(this.outVideoCurrentTime, 3)}</span>, 
    err = <span class="num">${rounding(this.timeErr, 3)} </span>
    rate = <span class="num">${rounding(this.playRate, 3)}</span>
  </div>
`;
        }
        return html`
  <video id="replay" class="size-${this.size}" src="${this.videoUrl}"></video>
  `;

    }
}
customElements.define('light9-vidref-replay', Light9VidrefReplay);
window.thresh=.3
window.p=.3
