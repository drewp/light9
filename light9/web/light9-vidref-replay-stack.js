import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import debug from '/lib/debug/debug-build-es6.js';
import _ from '/lib/underscore/underscore-min-es6.js';
import { rounding }  from '/node_modules/significant-rounding/index.js';

const log = debug('stack');

class Light9VidrefReplayStack extends LitElement {
    
    static get properties() {
        return {
            songTime: { type: Number, attribute: false }, // from musicState.t but higher res
            musicState: { type: Object, attribute: false },
            players: { type: Array, attribute: false },
            size: { type: String, attribute: true }
        };
    }

    constructor() {
        super();
        this.musicState = {};
    }

    setVideoTimesFromSongTime() {
        this.shadowRoot.querySelectorAll('light9-vidref-replay').forEach(
            (r) => {
                r.setVideoTimeFromSongTime(this.songTime, this.musicState.playing);
            });
    }
    nudgeTime(dt) {
        this.songTime += dt;
        log('song now', this.songTime);
    }
    fineTime() {
        if (this.musicState.playing) {
            const sinceLastUpdate = (Date.now() - this.musicState.reportTime) / 1000;
            this.songTime = sinceLastUpdate + this.musicState.tStart;
        } else if (this.lastFineTimePlayingState)  {
            this.songTime = this.musicState.t;
        }
        this.lastFineTimePlayingState = this.musicState.playing;
        requestAnimationFrame(this.fineTime.bind(this));
    }

    updated(changedProperties) {
        if (changedProperties.has('songTime')) {
            this.setVideoTimesFromSongTime();
        }
    }

    firstUpdated() {
        this.songTimeRangeInput = this.shadowRoot.querySelector('#songTime');

        const ws = reconnectingWebSocket('../ascoltami/time/stream',
                                         this.receivedSongAndTime.bind(this));
        reconnectingWebSocket('../vidref/time/stream', this.receivedRemoteScrubbedTime.bind(this));
        // bug: upon connecting, clear this.song
        this.fineTime();
    }

    receivedSongAndTime(msg) {
        this.musicState = msg;
        this.musicState.reportTime = Date.now();
        this.musicState.tStart = this.musicState.t;            

        this.songTimeRangeInput.max = this.musicState.duration;

        if (this.musicState.song != this.song) {
            this.song = this.musicState.song;
            this.getReplayMapForSong(this.song);
        }
    }

    receivedRemoteScrubbedTime(msg) {
        this.songTime = msg.st;

        // This doesn't work completely since it will keep getting
        // updates from ascoltami slow updates.
        if (msg.song != this.song) {
            this.song = msg.song;
            this.getReplayMapForSong(this.song);
        }
    }
        
    getReplayMapForSong(song) {
        const u = new URL(window.location.href);
        u.pathname = '/vidref/replayMap'
        u.searchParams.set('song', song);
        u.searchParams.set('maxClips', this.size == "small" ? '1' : '3');
        fetch(u.toString()).then((resp) => {
            if (resp.ok) {
                resp.json().then((msg) => {
                    this.players = msg.map(this.makeClipRow.bind(this));
                    this.updateComplete.then(this.setupClipRows.bind(this, msg));
                });
            }
        });          
    }
    
    setupClipRows(msg) {
        const nodes = this.shadowRoot.querySelectorAll('light9-vidref-replay');
        nodes.forEach((node, i) => {
            node.uri = msg[i].uri;
            node.videoUrl = msg[i].videoUrl;
            node.songToVideo = msg[i].songToVideo;
        });
        this.setVideoTimesFromSongTime();
    }
    
    makeClipRow(clip) {
        return html`<light9-vidref-replay @clips-changed="${this.onClipsChanged}" size="${this.size}"></light9-vidref-replay>`;
    }
    
    onClipsChanged(ev) {
        this.getReplayMapForSong(this.song);
    }
    
    disconnectedCallback() {
        log('bye');
        //close socket
    }

    userMovedSongTime(ev) {
        const st = this.songTimeRangeInput.valueAsNumber;
        this.songTime = st;

        fetch('/ascoltami/seekPlayOrPause', {
            method: 'POST',
            body: JSON.stringify({scrub: st}),
        });
    }

    static get styles() {
        return css`
        :host {
           display: inline-block;
        }
        #songTime {
            width: 100%;
        }
        #clips {
            display: flex;
            flex-direction: column;
        }
        a {
            color: rgb(97, 97, 255);
        }
        #songTime {
            font-size: 27px;
        }
        `;
    }
    
    render() {
        const songTimeRange = this.size != "small" ? html`<input id="songTime" type="range" 
           .value="${this.songTime}" 
           @input="${this.userMovedSongTime}" 
           min="0" max="0" step=".001"></div>
  <div><a href="${this.musicState.song}">${this.musicState.song}</a></div>
  <div id="songTime">showing song time ${rounding(this.songTime, 3)}</div>` : '';

        const globalCommands = this.size != 'small' ? html`
  <div>
    <button @click="${this.onClipsChanged}">Refresh clips for song</button>
  </div>
` : '';
        return html`
  <div>
    ${songTimeRange}
  <div>clips:</div>
  <div id="clips">
    ${this.players}
  </div>
  ${globalCommands}
`;

    }
}
customElements.define('light9-vidref-replay-stack', Light9VidrefReplayStack);
