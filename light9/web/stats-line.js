import { LitElement, TemplateResult, html, css } from '/node_modules/lit-element/lit-element.js';
import { rounding }  from '/node_modules/significant-rounding/index.js';

class StatsLine extends LitElement {
    
    static get properties() {
        return {
            name: {
                type: String,
                reflect: true,
                
            },
            stats: Object // to be refreshed with ws
        };
    }

    updated(changedProperties) {
        changedProperties.forEach((oldValue, propName) => {
            if (propName == 'name') {
                const reload = () => {
                    fetch(this.name + '/stats/?format=json').then((resp) => {
                        if (resp.ok) {
                    resp.json().then((msg) => {
                        
                        this.stats = msg;
                    setTimeout(reload, 1000);
                    });
                        }
                });
                }
                reload();
            }
        });
    }
    
    static get styles() {
        return css`
        :host {
            border: 2px solid #46a79f;
        }
        table { 
            border-collapse: collapse;
            background: #000;
            color: #ccc;
            font-family: sans-serif;
        }
        th, td { 
            outline: 1px solid #000; 
        }
        th {
            padding: 2px 4px;
            background: #2f2f2f;
        }
        td {
            padding: 0;
            vertical-align: top;
            text-align: center;
        }
        td.val {
            padding: 2px 4px;
            background: #3b5651;
        }
        .recents { 
            display: flex;
            align-items: flex-end;
            height: 30px;
        }
        .recents > div {
            width: 3px;
            background: red;
            border-right: 1px solid black;
        }
        .bigInt {
            min-width: 6em;
        }
        `;
    }
    
    render() {
        const table = (d, path) => {

            const cols = Object.keys(d);
            cols.sort();
            const th = (col) =>  {
                return html`<th>${col}</th>`;
            };
            const td = (col)  => {
                const cell = d[col];
                return html`${drawLevel(cell, path.concat(col))}`;
            };
            return html`
             <table>
               <tr>
                 ${cols.map(th)}
               </tr>
                 <tr>
                   ${cols.map(td)}
                 </tr>
             </table>`;
        };
        const tdWrap = (content) => {
            return html`<td>${content}</td>`;
        }
        const recents = (d, path) => {
            const hi = Math.max.apply(null, d.recents);
            const scl = 30 / hi;
            
            const bar = (y) => {
                let color;
                if (y < hi * .85) {
                    color="#6a6aff";
                } else {
                    color="#d09e4c";
                }
                return html`<div class="bar" style="height: ${y * scl}px; background: ${color};"></div>`;
            };
            return tdWrap(table({
                average: rounding(d.average, 3),
                recents: html`<div class="recents">${d.recents.map(bar)}</div>`
            }, path));

        };
        const pmf = (d, path) => {
            return tdWrap(table({
                count: d.count,
                'values [ms]': html`
                   <div>mean=${rounding(d.mean*1000, 3)}</div>
                   <div>sd=${rounding(d.stddev*1000, 3)}</div>
                   <div>99=${rounding(d['99percentile']*1000, 3)}</div>
                 `
            }, path));
        };
        const drawLevel = (d, path) => {           
            if (typeof d === 'object') {
                if (d instanceof TemplateResult) {
                    return html`<td class="val">${d}</td>`;
                } else if (d.count !== undefined && d.min !== undefined) {
                    return pmf(d, path);
                } else if (d.average !== undefined && d.recents !== undefined) {
                    return recents(d, path);
                } else {
                    return tdWrap(table(d, path));
                }
            } else {             
                return html`<td class="val bigInt">${d}</td>`;
            }
        };
        return table(this.stats || {}, []);
    }
}
customElements.define('stats-line', StatsLine);
