/* Free page. Direct downloads, an instant key, and an optional update opt-in. */
(function () {
    'use strict';

    var useLocalApi = new URLSearchParams(window.location.search).get('localapi') === '1';
    var API_BASE = useLocalApi ? 'http://localhost:5001' : 'https://api.nodecontrol.io';
    var ATTR_KEY = 'nc_attr';
    /* TODO: remove the redeem box after 2027-02-17 (90 days from 19 Nov 2026). */
    var REDEEM_BOX_UNTIL = '2027-02-17';

    function clip(value, max) {
        return String(value || '').slice(0, max);
    }

    function externalReferrerHost() {
        try {
            var ref = document.referrer ? new URL(document.referrer) : null;
            if (ref && ref.hostname && ref.hostname !== window.location.hostname) {
                return ref.hostname;
            }
        } catch (err) { /* leave it empty */ }
        return '';
    }

    function rememberAttribution() {
        try {
            if (sessionStorage.getItem(ATTR_KEY)) return;
            var params = new URLSearchParams(window.location.search);
            var source = params.get('utm_source') || '';
            var medium = params.get('utm_medium') || '';
            var campaign = params.get('utm_campaign') || '';
            var content = params.get('utm_content') || '';
            if (!source && !medium && !campaign && !content) return;
            sessionStorage.setItem(ATTR_KEY, JSON.stringify({
                utm_source: source,
                utm_medium: medium,
                utm_campaign: campaign,
                utm_content: content,
                referrer: externalReferrerHost(),
                landing_page: window.location.pathname
            }));
        } catch (err) { /* the download still works */ }
    }

    function attributionPayload() {
        var params = new URLSearchParams(window.location.search);
        var current = {
            utm_source: clip(params.get('utm_source'), 64),
            utm_medium: clip(params.get('utm_medium'), 64),
            utm_campaign: clip(params.get('utm_campaign'), 128),
            utm_content: clip(params.get('utm_content'), 128),
            referrer: clip(externalReferrerHost(), 128),
            landing_page: clip(window.location.pathname, 256)
        };
        if (current.utm_source || current.utm_medium || current.utm_campaign || current.utm_content) {
            return current;
        }
        try {
            var raw = sessionStorage.getItem(ATTR_KEY);
            var parsed = raw ? JSON.parse(raw) : null;
            if (parsed && typeof parsed === 'object') {
                return {
                    utm_source: clip(parsed.utm_source, 64),
                    utm_medium: clip(parsed.utm_medium, 64),
                    utm_campaign: clip(parsed.utm_campaign, 128),
                    utm_content: clip(parsed.utm_content, 128),
                    referrer: clip(parsed.referrer, 128),
                    landing_page: clip(parsed.landing_page, 256)
                };
            }
        } catch (err) { /* use the current link */ }
        return current;
    }

    function utmQuery() {
        var attr = attributionPayload();
        var params = new URLSearchParams();
        ['utm_source', 'utm_campaign', 'utm_content'].forEach(function (key) {
            if (attr[key]) params.set(key, attr[key]);
        });
        var text = params.toString();
        return text ? '?' + text : '';
    }

    function trackFunnel(eventName) {
        var attr = attributionPayload();
        var body = JSON.stringify({
            event: eventName,
            utm_source: attr.utm_source,
            utm_campaign: attr.utm_campaign,
            utm_content: attr.utm_content
        });
        try {
            if (navigator.sendBeacon) {
                navigator.sendBeacon(API_BASE + '/api/funnel-event', new Blob([body], { type: 'text/plain' }));
                return;
            }
        } catch (err) { /* fall through */ }
        fetch(API_BASE + '/api/funnel-event', {
            method: 'POST',
            headers: { 'Content-Type': 'text/plain' },
            body: body,
            keepalive: true
        }).catch(function () {});
    }

    function showMessage(text) {
        var node = document.getElementById('freeDownloadMessage');
        if (!node) return;
        node.hidden = !text;
        node.textContent = text || '';
    }

    function showKey(code) {
        var block = document.getElementById('freeKeyBlock');
        var value = document.getElementById('freeKeyValue');
        if (!block || !value) return;
        value.textContent = code;
        block.hidden = false;
    }

    function downloadUrl(platform) {
        return API_BASE + '/api/v1/download/free/latest/' + platform + utmQuery();
    }

    function startDownload(platform) {
        showMessage('');
        trackFunnel(platform === 'win' ? 'free_download_click_win' : 'free_download_click_mac');
        var attr = attributionPayload();
        fetch(API_BASE + '/api/free/instant-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform: platform,
                utm_source: attr.utm_source,
                utm_medium: attr.utm_medium,
                utm_campaign: attr.utm_campaign,
                utm_content: attr.utm_content,
                referrer: attr.referrer,
                landing_page: attr.landing_page
            })
        }).then(function (res) {
            return res.json().then(function (body) {
                return { ok: res.ok, status: res.status, body: body };
            });
        }).then(function (result) {
            var code = result.body && result.body.licence_key;
            if (code) showKey(code);
            else if (result.body && result.body.error && result.body.error.message) {
                showMessage(result.body.error.message);
            } else if (result.body && result.body.message) {
                showMessage(result.body.message);
            } else {
                showMessage('The download can still start. The licence key was not issued.');
            }
            window.location.href = downloadUrl(platform);
        }).catch(function () {
            showMessage('The download can still start. The licence key was not issued.');
            window.location.href = downloadUrl(platform);
        });
    }

    function loadMeta() {
        fetch(API_BASE + '/api/v1/download/free/latest').then(function (res) {
            if (!res.ok) return null;
            return res.json();
        }).then(function (body) {
            if (!body) return;
            var node = document.getElementById('freeReleaseMeta');
            if (!node) return;
            var parts = [];
            if (body.version) parts.push('Version ' + body.version);
            ['mac', 'win'].forEach(function (platform) {
                var item = body[platform];
                if (!item) return;
                var label = platform === 'mac' ? 'macOS' : 'Windows';
                var size = item.size ? Math.round(item.size / 1048576) + ' MB' : '';
                parts.push(label + (size ? ' ' + size : ''));
                if (item.sha256) parts.push(label + ' SHA-256 ' + item.sha256);
            });
            node.textContent = parts.join('. ') + '.';
        }).catch(function () {});
    }

    function orderButtons() {
        var row = document.getElementById('freeDownloadActions');
        if (!row) return;
        var mac = row.querySelector('[data-platform="mac"]');
        var win = row.querySelector('[data-platform="win"]');
        var windows = /Win/.test(navigator.platform || '') || /Windows/.test(navigator.userAgent || '');
        if (windows && win && mac) {
            row.insertBefore(win, mac);
            win.classList.add('btn-primary');
            win.classList.remove('btn-outline');
            mac.classList.add('btn-outline');
            mac.classList.remove('btn-primary');
        }
    }

    rememberAttribution();
    trackFunnel('free_page_view');
    loadMeta();
    orderButtons();

    document.querySelectorAll('[data-free-download]').forEach(function (button) {
        button.addEventListener('click', function (event) {
            event.preventDefault();
            startDownload(button.getAttribute('data-platform'));
        });
    });

    var copyBtn = document.getElementById('freeKeyCopy');
    if (copyBtn) {
        copyBtn.addEventListener('click', function () {
            var value = document.getElementById('freeKeyValue');
            var text = value ? value.textContent : '';
            if (!text || !navigator.clipboard) return;
            navigator.clipboard.writeText(text).then(function () {
                copyBtn.textContent = 'Copied';
            }).catch(function () {});
        });
    }

    var optIn = document.getElementById('freeOptIn');
    if (optIn) {
        optIn.addEventListener('submit', function (event) {
            event.preventDefault();
            var result = document.getElementById('freeOptInResult');
            var email = document.getElementById('freeOptInEmail');
            var consent = document.getElementById('freeOptInConsent');
            if (!consent || !consent.checked) {
                if (result) result.textContent = 'Tick the box if you want update email.';
                return;
            }
            var attr = attributionPayload();
            var keyEl = document.getElementById('freeKeyValue');
            var licenceKey = keyEl ? (keyEl.textContent || '').trim() : '';
            var body = {
                email: email ? email.value : '',
                consent: true,
                consent_text_version: 'v1',
                source: 'free_page',
                platform: /Win/.test(navigator.platform || '') ? 'win' : 'mac',
                utm_source: attr.utm_source,
                utm_campaign: attr.utm_campaign,
                utm_content: attr.utm_content
            };
            if (/^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(licenceKey)) {
                body.licence_key = licenceKey;
            }
            fetch(API_BASE + '/api/free/updates/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            }).then(function (res) {
                return res.json().then(function (body) {
                    return { ok: res.ok, body: body };
                });
            }).then(function (payload) {
                var message = (payload.body && (payload.body.message || (payload.body.error && payload.body.error.message))) || 'Check your email to confirm.';
                if (result) result.textContent = message;
            }).catch(function () {
                if (result) result.textContent = 'The request did not finish. Try again.';
            });
        });
    }

    var redeemToggle = document.getElementById('freeRedeemToggle');
    var redeemForm = document.getElementById('redeemForm');
    if (redeemToggle && redeemForm) {
        redeemToggle.addEventListener('click', function () {
            redeemForm.hidden = !redeemForm.hidden;
        });
    }

    var redeemWrap = document.getElementById('redeem');
    if (redeemWrap && new Date().toISOString().slice(0, 10) > REDEEM_BOX_UNTIL) {
        redeemWrap.hidden = true;
    }

    var params = new URLSearchParams(window.location.search);
    var requested = params.get('platform');
    if (requested === 'mac' || requested === 'win') {
        startDownload(requested);
    }

    var redeemBtn = document.getElementById('redeemBtn');
    var redeemCode = document.getElementById('redeemCode');
    var redeemResult = document.getElementById('redeemResult');
    if (redeemBtn && redeemCode && redeemResult) {
        redeemBtn.addEventListener('click', function () {
            var code = redeemCode.value.trim();
            redeemResult.textContent = '';
            fetch(API_BASE + '/api/redeem', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code })
            }).then(function (res) {
                return res.json().then(function (body) {
                    return { ok: res.ok, body: body };
                });
            }).then(function (payload) {
                if (!payload.ok) {
                    var err = payload.body && payload.body.error;
                    redeemResult.textContent = (err && err.message) || (typeof err === 'string' ? err : '') || (payload.body && payload.body.message) || 'That code was not accepted.';
                    return;
                }
                var downloads = payload.body.downloads || {};
                redeemResult.textContent = '';
                ['mac', 'win'].forEach(function (platform) {
                    if (!downloads[platform]) return;
                    var link = document.createElement('a');
                    link.href = downloads[platform];
                    link.textContent = platform === 'mac' ? 'Download macOS' : 'Download Windows';
                    link.style.display = 'inline-block';
                    link.style.marginRight = '12px';
                    redeemResult.appendChild(link);
                });
            }).catch(function () {
                redeemResult.textContent = 'The request did not finish. Try again.';
            });
        });
    }
})();
