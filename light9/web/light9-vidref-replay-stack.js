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
            players: { type: Array, attribute: false }
        };
    }

    constructor() {
        super();
        this.musicState = {};
    }

    setVideoTimesFromSongTime() {
        this.shadowRoot.querySelectorAll('light9-vidref-replay').forEach(
            (r) => {
                r.setVideoTimeFromSongTime(this.songTime);
            });
    }

    fineTime() {       
        if (this.musicState.playing) {
            const sinceLastUpdate = (Date.now() - this.musicState.reportTime) / 1000;
            this.songTime = sinceLastUpdate + this.musicState.tStart;
            this.songTimeRangeInput.value = this.songTime;
        } else  {
            //this.songTime = this.musicState.t;
        }
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
        
    getReplayMapForSong(song) {
        const u = new URL(window.location.href);
        u.pathname = '/vidref/replayMap'
        u.searchParams.set('song', song);
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
        return html`<light9-vidref-replay @clips-changed="${this.onClipsChanged}"></light9-vidref-replay>`;
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
         
        }
        #songTime {
            width: 100%;
        }
#clips {
display: flex;
flex-direction: column;
}
        `;
    }
    
    render() {
        return html`
<div>
  <div><input id="songTime" type="range" @input="${this.userMovedSongTime}" min="0" max="0" step=".001"></div>
  <div>${this.musicState.song}</div>
  <div>showing song time ${rounding(this.songTime, 3)} (${rounding(this.musicState.t, 3)})</div>
<div>clips:</div>
<div id="clips">
   ${this.players}
</div>
</div>
`;

    }
}
customElements.define('light9-vidref-replay-stack', Light9VidrefReplayStack);
