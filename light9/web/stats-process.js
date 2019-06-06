import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import debug from '/lib/debug/debug-build-es6.js';
import { rounding }  from '/node_modules/significant-rounding/index.js';

const log = debug('process');

const remap = (x, lo, hi, outLo, outHi) => {
    return outLo + (outHi - outLo) * Math.max(0, Math.min(1, (x - lo) / (hi - lo)));
};

class StatsProcess extends LitElement {
    
    static get properties() {
        return {
            data: { type: Object },
        };
    }

    firstUpdated() {
        // inspired by https://codepen.io/qiruiyin/pen/qOopQx
        var context = this.shadowRoot.firstElementChild,
	    ctx = context.getContext('2d'),
	    w = 64,
	    h = 64,
	    revs = 0;   
	
	context.width = w;
	context.height = h;

        let prev = Date.now() / 1000;

        var animate = () => {
	    requestAnimationFrame( animate );

            const now = Date.now() / 1000;
            ctx.beginPath();
            // wrong type of fade- never goes to 0
            ctx.fillStyle = '#00000003';
            ctx.fillRect(0, 0, w, h);
            if (this.data.time < now - 2) {
                return;
            }
            const dt = now - prev;
            prev = now;

            const size = remap(this.data.memMb, /*in*/ 20, 600, /*out*/ 3, 30);
	    revs += dt * remap(this.data.cpuPercent, /*in*/ 0, 100, /*out*/ 4, 120);
            const rad  = remap(size, /*in*/ 3, 30, /*out*/ 14, 5);

	    var x = w/2 + rad * Math.cos(revs / 6.28),
		y = h/2 + rad * Math.sin(revs / 6.28);

	    ctx.save();
	    ctx.beginPath();
	    ctx.fillStyle = "hsl(194, 100%, 42%)";
	    ctx.arc(x, y, size, 0, 2*Math.PI);
	    ctx.fill();
	    ctx.restore();
	    
        };
        animate();
    }
    
    updated(changedProperties) {
        if (changedProperties.has('data')) {
            this.shadowRoot.firstElementChild.setAttribute('title', `cpu ${this.data.cpuPercent}% mem ${this.data.memMb}MB`);
        }
    }

    static get styles() {
        return css`
        :host {
           display: inline-block;
           width: 64px;
           height: 64px;
        }
        `;
    }
    
    render() {
        return html`<canvas></canvas>`;

    }
}
customElements.define('stats-process', StatsProcess);

