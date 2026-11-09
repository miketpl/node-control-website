/* Proves the ad tags stay idle while NC_ADS.enabled is false.
   Run: node js/conversions-off.test.mjs
   From the repo root. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const root = new URL('..', import.meta.url);
const js = fs.readFileSync(new URL('js/conversions.js', root), 'utf8');
const html = fs.readFileSync(new URL('index.html', root), 'utf8');
const freeHtml = fs.readFileSync(new URL('free/index.html', root), 'utf8');
const privacy = fs.readFileSync(new URL('privacy.html', root), 'utf8');
const css = fs.readFileSync(new URL('css/style.css', root), 'utf8');

assert.match(js, /enabled:\s*false/);
assert.doesNotMatch(html, /redditstatic|googletagmanager|googleadservices|google-analytics/i);
assert.doesNotMatch(freeHtml, /redditstatic|googletagmanager|googleadservices|google-analytics/i);
assert.doesNotMatch(privacy, /redditstatic|googletagmanager|REDDIT_PIXEL_ID|Allow advertising measurement/i);
assert.match(css, /#nc-consent-reject,\s*#nc-consent-accept/);

const requests = [];
function element(tag) {
    return {
        tagName: tag,
        async: false,
        src: '',
        set srcAssigned(value) { this.src = value; requests.push(value); },
        setAttribute(name, value) { if (name === 'src') requests.push(value); },
        appendChild() {},
        addEventListener() {},
        remove() {},
        style: {}
    };
}

const document = {
    body: { appendChild() { requests.push('banner'); } },
    head: { appendChild(node) { if (node.src) requests.push(node.src); } },
    readyState: 'complete',
    getElementById() { return null; },
    createElement: element,
    addEventListener() { requests.push('listener'); },
    dispatchEvent(event) {
        return true;
    }
};

const localStorage = {
    getItem() { requests.push('storage-read'); return null; },
    setItem() { requests.push('storage-write'); }
};

const context = {
    window: null,
    document,
    localStorage,
    navigator: { sendBeacon() { requests.push('beacon'); } },
    fetch() { requests.push('fetch'); },
    XMLHttpRequest: function () { requests.push('xhr'); },
    Image: function () { requests.push('image'); },
    CustomEvent: class CustomEvent {
        constructor(type, init) { this.type = type; this.detail = init && init.detail; }
    },
    Date,
    encodeURIComponent
};
context.window = context;
vm.createContext(context);
vm.runInContext(js, context);
context.document.dispatchEvent(new context.CustomEvent('nc-conversion', { detail: { name: 'sign_up' } }));
context.document.dispatchEvent(new context.CustomEvent('nc-conversion', { detail: { name: 'download' } }));

assert.deepEqual(requests, [], 'third-party or consent work ran while the flag is off: ' + requests.join(','));
console.log('conversions stay off: no banner, no storage, no third-party request');
