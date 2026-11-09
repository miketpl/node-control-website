/* Free landing page only. Same licence API as the main page. */
(function () {
    'use strict';

    var useLocalApi = new URLSearchParams(window.location.search).get('localapi') === '1';
    var API_BASE = useLocalApi ? 'http://localhost:5001' : 'https://api.nodecontrol.io';
    var ATTR_KEY = 'nc_attr';

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
                landing_page: window.location.pathname,
            }));
        } catch (err) { /* sign-up still works */ }
    }

    function storedAttribution() {
        try {
            var raw = sessionStorage.getItem(ATTR_KEY);
            if (!raw) return null;
            var parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            return {
                utm_source: clip(parsed.utm_source, 64),
                utm_medium: clip(parsed.utm_medium, 64),
                utm_campaign: clip(parsed.utm_campaign, 128),
                utm_content: clip(parsed.utm_content, 128),
                referrer: clip(parsed.referrer, 128),
                landing_page: clip(parsed.landing_page, 256),
            };
        } catch (err) {
            return null;
        }
    }

    function attributionPayload() {
        var params = new URLSearchParams(window.location.search);
        var current = {
            utm_source: clip(params.get('utm_source'), 64),
            utm_medium: clip(params.get('utm_medium'), 64),
            utm_campaign: clip(params.get('utm_campaign'), 128),
            utm_content: clip(params.get('utm_content'), 128),
            referrer: clip(externalReferrerHost(), 128),
            landing_page: clip(window.location.pathname, 256),
        };
        if (current.utm_source || current.utm_medium || current.utm_campaign || current.utm_content) {
            return current;
        }
        return storedAttribution() || current;
    }

    rememberAttribution();

    function funnelCampaign() {
        try {
            var params = new URLSearchParams(window.location.search);
            var source = params.get('utm_source') || '';
            var campaign = params.get('utm_campaign') || '';
            var content = params.get('utm_content') || '';
            if (!source && !campaign && !content) {
                var stored = storedAttribution();
                source = stored ? (stored.utm_source || '') : '';
                campaign = stored ? (stored.utm_campaign || '') : '';
                content = stored ? (stored.utm_content || '') : '';
            }
            return { utm_source: source, utm_campaign: campaign, utm_content: content };
        } catch (err) {
            return { utm_source: '', utm_campaign: '', utm_content: '' };
        }
    }

    function trackFunnel(event) {
        try {
            if (!navigator.sendBeacon) return;
            var tags = funnelCampaign();
            var body = JSON.stringify({
                event: event,
                utm_source: tags.utm_source,
                utm_campaign: tags.utm_campaign,
                utm_content: tags.utm_content,
            });
            navigator.sendBeacon(API_BASE + '/api/funnel-event',
                new Blob([body], { type: 'text/plain' }));
        } catch (err) { /* never block the page */ }
    }

    function watchFreeFunnel() {
        var seenView = false;
        var seenStart = false;
        var section = document.getElementById('free-edition');
        if (section && typeof IntersectionObserver === 'function') {
            try {
                var observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (seenView || entry.intersectionRatio < 0.5) return;
                        seenView = true;
                        trackFunnel('free_section_view');
                        observer.disconnect();
                    });
                }, { threshold: [0.5] });
                observer.observe(section);
            } catch (err) { /* leave the page alone */ }
        }
        var form = document.getElementById('freeRequestForm');
        if (!form) return;
        function markStart() {
            if (seenStart) return;
            seenStart = true;
            trackFunnel('free_form_start');
            form.removeEventListener('focusin', markStart);
            form.removeEventListener('input', markStart);
        }
        form.addEventListener('focusin', markStart);
        form.addEventListener('input', markStart);
    }

    watchFreeFunnel();

    // The form is visible unless the status call succeeds and says paused.
    var downloadSection = document.getElementById('download');
    if (downloadSection) downloadSection.classList.remove('free-paused');
    var statusOptions = { headers: { 'Accept': 'application/json' } };
    if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
        statusOptions.signal = AbortSignal.timeout(8000);
    }
    fetch(API_BASE + '/api/v1/status', statusOptions)
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
            if (!downloadSection || !data || data.free_downloads_paused !== true) return;
            downloadSection.classList.add('free-paused');
            var notice = document.getElementById('free-paused-notice');
            if (notice) notice.textContent = 'Free downloads are temporarily paused';
        })
        .catch(function () {});

    function showResult(container, message, type) {
        container.className = 'redeem-result visible ' + type;
        if (type === 'success') {
            container.innerHTML = message;
        } else {
            container.textContent = message;
        }
    }

    async function apiCall(endpoint, data) {
        var res = await fetch(API_BASE + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return { status: res.status, data: await res.json() };
    }

    var pendingEmail = '';
    var freeForm = document.getElementById('freeRequestForm');
    var verifySection = document.getElementById('verifySection');
    var downloadCodeSection = document.getElementById('downloadCodeSection');
    var reqResult = document.getElementById('reqResult');

    if (freeForm) {
        freeForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            trackFunnel('free_form_submit');
            var btn = document.getElementById('reqSubmitBtn');
            var name = document.getElementById('reqName').value.trim();
            var email = document.getElementById('reqEmail').value.trim();
            var platform = document.getElementById('reqPlatform').value;
            var company = document.getElementById('reqCompany').value.trim();
            if (!name || !email || !platform) {
                showResult(reqResult, 'Please fill in all required fields.', 'error');
                return;
            }
            btn.textContent = 'Sending…';
            btn.style.opacity = '0.6';
            btn.style.pointerEvents = 'none';
            reqResult.className = 'redeem-result';
            try {
                var result = await apiCall('/api/request-access',
                    Object.assign({ name: name, email: email, company: company, platform: platform }, attributionPayload()));
                if (result.data.success) {
                    signalConversion('sign_up');
                    pendingEmail = email;
                    freeForm.style.display = 'none';
                    verifySection.style.display = 'block';
                    document.getElementById('verifyEmailDisplay').textContent = email;
                    document.getElementById('verifyCode').focus();
                } else {
                    showResult(reqResult, result.data.error || 'Something went wrong. Please try again.', 'error');
                    btn.textContent = 'Get Node Control Free';
                    btn.style.opacity = '';
                    btn.style.pointerEvents = '';
                }
            } catch (err) {
                showResult(reqResult, 'Connection error. Please try again.', 'error');
                btn.textContent = 'Get Node Control Free';
                btn.style.opacity = '';
                btn.style.pointerEvents = '';
            }
        });
    }

    var verifyBtn = document.getElementById('verifyBtn');
    var verifyCodeInput = document.getElementById('verifyCode');
    var verifyResult = document.getElementById('verifyResult');
    var resendBtn = document.getElementById('resendBtn');

    if (verifyBtn) {
        async function doVerify() {
            var code = verifyCodeInput.value.trim();
            if (!code || code.length < 6) {
                showResult(verifyResult, 'Please enter the 6-digit code from your email.', 'error');
                return;
            }
            verifyBtn.textContent = 'Verifying…';
            verifyBtn.style.opacity = '0.6';
            try {
                var result = await apiCall('/api/verify', { email: pendingEmail, code: code });
                if (result.data.success) {
                    verifySection.style.display = 'none';
                    downloadCodeSection.style.display = 'block';
                    document.getElementById('revealedCode').textContent = result.data.download_code;
                    var redeemInput = document.getElementById('redeemCode');
                    if (redeemInput) {
                        redeemInput.value = result.data.download_code;
                        setTimeout(function () { document.getElementById('redeemBtn').click(); }, 500);
                    }
                } else {
                    showResult(verifyResult, result.data.error || 'Invalid code. Please try again.', 'error');
                    verifyBtn.textContent = 'Verify';
                    verifyBtn.style.opacity = '';
                }
            } catch (err) {
                showResult(verifyResult, 'Connection error. Please try again.', 'error');
                verifyBtn.textContent = 'Verify';
                verifyBtn.style.opacity = '';
            }
        }
        verifyBtn.addEventListener('click', doVerify);
        verifyCodeInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); doVerify(); }
        });
    }

    if (resendBtn) {
        resendBtn.addEventListener('click', async function () {
            if (!pendingEmail) return;
            this.textContent = 'Resending…';
            this.style.pointerEvents = 'none';
            try {
                var name = document.getElementById('reqName').value.trim();
                var platform = document.getElementById('reqPlatform').value;
                var company = document.getElementById('reqCompany').value.trim();
                await apiCall('/api/request-access',
                    Object.assign({ name: name, email: pendingEmail, company: company, platform: platform }, attributionPayload()));
                this.textContent = 'Code resent. Check your inbox.';
            } catch (err) {
                this.textContent = 'Failed to resend. Try again.';
            }
            var button = this;
            setTimeout(function () {
                button.textContent = "Didn't receive it? Resend code";
                button.style.pointerEvents = '';
            }, 5000);
        });
    }

    function signalConversion(name) {
        try {
            document.dispatchEvent(new CustomEvent('nc-conversion', { detail: { name: name } }));
        } catch (err) { /* the page still works */ }
    }

    function trackDownload(code, platform, kind) {
        if (kind === 'click') signalConversion('download');
        try {
            var tags = funnelCampaign();
            var body = JSON.stringify({
                code: code,
                platform: platform,
                kind: kind,
                utm_source: tags.utm_source,
                utm_campaign: tags.utm_campaign,
                utm_content: tags.utm_content,
            });
            if (navigator.sendBeacon) {
                navigator.sendBeacon(API_BASE + '/api/download-event',
                    new Blob([body], { type: 'text/plain' }));
            }
        } catch (err) { /* never block the download */ }
    }

    function startDownload(url) {
        var a = document.createElement('a');
        a.href = url;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { a.remove(); }, 1000);
    }

    function isInstallerUrl(url) {
        if (!url) return false;
        if (/\.(dmg|exe)(\?|#|$)/i.test(url)) return true;
        try {
            var parsed = new URL(url, window.location.href);
            return /\/api\/v1\/download\/free\/(mac|win)$/i.test(parsed.pathname);
        } catch (err) {
            return false;
        }
    }

    var redeemBtn = document.getElementById('redeemBtn');
    var redeemCode = document.getElementById('redeemCode');
    var redeemResult = document.getElementById('redeemResult');

    if (redeemBtn && redeemCode && redeemResult) {
        async function validateCode(code) {
            var normalised = code.trim().toUpperCase().replace(/\s+/g, '-');
            if (!normalised) {
                showResult(redeemResult, 'Please enter a download code.', 'error');
                return;
            }
            redeemBtn.textContent = 'Checking…';
            redeemBtn.style.opacity = '0.6';
            try {
                var result = await apiCall('/api/redeem', { code: normalised });
                var data = result.data;
                if (data.success) {
                    var urls = data.downloads;
                    var platformSelect = document.getElementById('reqPlatform');
                    var chosen = platformSelect ? platformSelect.value : '';
                    var key = chosen === 'macos' ? 'mac' : chosen === 'windows' ? 'win' : null;
                    if (key && isInstallerUrl(urls[key])) {
                        var other = key === 'mac' ? 'win' : 'mac';
                        var otherLabel = key === 'mac' ? 'Windows (.exe)' : 'macOS (.dmg)';
                        startDownload(urls[key]);
                        trackDownload(normalised, key, 'auto');
                        showResult(redeemResult,
                            '<strong>' + data.label + '</strong> — your download is starting.' +
                            '<div class="redeem-download-links">' +
                            '<a href="' + urls[key] + '" data-platform="' + key + '">Download didn\'t start? Click here.</a>' +
                            '</div>' +
                            '<a href="' + urls[other] + '" data-platform="' + other + '">Need ' + otherLabel + ' instead?</a>',
                            'success');
                    } else {
                        showResult(redeemResult,
                            '<strong>' + data.label + '</strong> — choose your platform:' +
                            '<div class="redeem-download-links">' +
                            '<a href="' + urls.mac + '" class="btn btn-outline btn-sm" data-platform="mac">macOS (.dmg)</a>' +
                            '<a href="' + urls.win + '" class="btn btn-outline btn-sm" data-platform="win">Windows (.exe)</a>' +
                            '</div>',
                            'success');
                    }
                    redeemResult.querySelectorAll('a[data-platform]').forEach(function (link) {
                        link.addEventListener('click', function () {
                            trackDownload(normalised, link.getAttribute('data-platform'), 'click');
                        });
                    });
                } else {
                    showResult(redeemResult, data.error || 'Invalid code. Please try again.', 'error');
                }
            } catch (err) {
                showResult(redeemResult, 'Connection error. Please try again.', 'error');
            }
            redeemBtn.textContent = 'Redeem';
            redeemBtn.style.opacity = '';
        }
        redeemBtn.addEventListener('click', function () { validateCode(redeemCode.value); });
        redeemCode.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); validateCode(redeemCode.value); }
        });
    }
})();
