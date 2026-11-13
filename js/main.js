/* ══════════════════════════════════════════════════════════════
   NodeControl Website — main.js
   ══════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    // ── Mobile nav toggle ────────────────────────────────────
    const toggle = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');

    if (toggle && links) {
        toggle.addEventListener('click', () => {
            toggle.classList.toggle('active');
            links.classList.toggle('active');
        });

        // Close menu when a link is clicked
        links.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                toggle.classList.remove('active');
                links.classList.remove('active');
            });
        });
    }

    // ── Navbar background on scroll ──────────────────────────
    const navbar = document.getElementById('navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.style.background = 'rgba(11, 15, 20, 0.98)';
            } else {
                navbar.style.background = 'rgba(11, 15, 20, 0.92)';
            }
        });
    }

    // ── Active nav link tracking ─────────────────────────────
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-links a');

    function setActiveLink() {
        const scrollPos = window.scrollY + 120;

        sections.forEach(section => {
            const top = section.offsetTop;
            const height = section.offsetHeight;
            const id = section.getAttribute('id');

            if (scrollPos >= top && scrollPos < top + height) {
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + id) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }

    window.addEventListener('scroll', setActiveLink);
    setActiveLink();

    // ── License API Configuration ────────────────────────────────
    // Local previews talk to the live API. Run the Flask backend locally
    // (flask --app app run --port 5001) and add ?localapi=1 to the URL to
    // target it instead. Port 5001 because macOS AirPlay squats 5000.
    const useLocalApi = new URLSearchParams(window.location.search).get('localapi') === '1';
    const API_BASE = useLocalApi
        ? 'http://localhost:5001'
        : 'https://api.nodecontrol.io';

    // The form is visible unless this call succeeds and says downloads are
    // paused. A failed, blocked, or timed-out call leaves the form up.
    // The server still refuses a sign-up while downloads are paused.
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

    // Professional checkout is the call to action. The owner turned this on.
    // true: Subscribe buttons open the email form and POST /api/checkout.
    // false: those buttons are hidden. The Free download button stays a download.
    const PRO_CHECKOUT_LIVE = true;

    function selectedProPlan() {
        const checked = document.querySelector('input[name="proPlan"]:checked');
        return checked ? checked.value : 'monthly';
    }

    function renderProPrice() {
        const price = document.getElementById('proPriceDisplay');
        const note = document.getElementById('proPriceNote');
        if (!price || !note) return;
        if (selectedProPlan() === 'annual') {
            price.innerHTML = '£21.25<span>/mo</span>';
            note.textContent = '£21.25/mo billed annually. £255/year. Save 15%.';
        } else {
            price.innerHTML = '£25<span>/month</span>';
            note.textContent = 'Or £255/year (£21.25/mo billed annually, save 15%).';
        }
    }

    document.querySelectorAll('input[name="proPlan"]').forEach(function (input) {
        input.addEventListener('change', renderProPrice);
    });
    renderProPrice();

    if (!PRO_CHECKOUT_LIVE) {
        document.querySelectorAll('.pro-checkout').forEach(function (el) {
            el.classList.add('payment-pending');
        });
    }

    const checkoutDialog = document.getElementById('proCheckoutDialog');
    const checkoutForm = document.getElementById('proCheckoutForm');
    const checkoutEmail = document.getElementById('proCheckoutEmail');
    const checkoutError = document.getElementById('proCheckoutError');
    const checkoutSubmit = document.getElementById('proCheckoutSubmit');
    const checkoutClose = document.getElementById('proCheckoutClose');
    let checkoutAttempt = 0;

    function showCheckoutError(message) {
        if (!checkoutError) return;
        checkoutError.textContent = message;
        checkoutError.className = 'redeem-result visible error';
    }

    function clearCheckoutError() {
        if (!checkoutError) return;
        checkoutError.textContent = '';
        checkoutError.className = 'redeem-result';
    }

    function setCheckoutBusy(busy) {
        if (!checkoutSubmit) return;
        checkoutSubmit.disabled = busy;
        checkoutSubmit.textContent = busy ? 'Starting checkout…' : 'Continue to checkout';
        checkoutSubmit.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    function selectedCheckoutPlan() {
        const checked = document.querySelector('#proCheckoutDialog input[name="checkoutPlan"]:checked');
        if (!checked) return '';
        return checked.value;
    }

    function validCheckoutEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    function checkoutErrorMessage(status) {
        if (status === 429) {
            return 'Too many checkout attempts from this network. Wait a while and try again.';
        }
        if (status === 503) {
            return 'Checkout is not available right now. Try again later.';
        }
        if (status === 400) {
            return 'Choose monthly or annual, and enter a valid email.';
        }
        return 'Checkout could not be started. Try again in a moment.';
    }

    function checkoutUrl(value) {
        try {
            const url = new URL(value);
            if (url.protocol === 'https:' || url.protocol === 'http:') return url.href;
        } catch (err) { /* not a URL */ }
        return '';
    }

    function openProCheckout() {
        if (!PRO_CHECKOUT_LIVE || !checkoutDialog || typeof checkoutDialog.showModal !== 'function') return;
        const pagePlan = selectedProPlan();
        const match = checkoutDialog.querySelector('input[name="checkoutPlan"][value="' + pagePlan + '"]');
        if (match) match.checked = true;
        clearCheckoutError();
        if (checkoutEmail) checkoutEmail.removeAttribute('aria-invalid');
        if (!checkoutDialog.open) checkoutDialog.showModal();
    }

    async function startProCheckout(plan, email) {
        const attempt = ++checkoutAttempt;
        setCheckoutBusy(true);
        clearCheckoutError();
        try {
            const res = await fetch(API_BASE + '/api/checkout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ plan: plan, email: email })
            });
            let data = {};
            try {
                data = await res.json();
            } catch (err) {
                data = {};
            }
            if (attempt !== checkoutAttempt || !checkoutDialog || !checkoutDialog.open) return;
            const url = checkoutUrl(data && data.url);
            if (!res.ok || !url) {
                showCheckoutError(checkoutErrorMessage(res.ok ? 502 : res.status));
                setCheckoutBusy(false);
                return;
            }
            window.location.assign(url);
        } catch (err) {
            if (attempt !== checkoutAttempt || !checkoutDialog || !checkoutDialog.open) return;
            showCheckoutError('Could not reach the licence service. Check your connection and try again.');
            setCheckoutBusy(false);
        }
    }

    document.querySelectorAll('[data-pro-checkout]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            openProCheckout();
        });
    });

    if (checkoutForm) {
        checkoutForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (!PRO_CHECKOUT_LIVE || !checkoutEmail || !checkoutSubmit || checkoutSubmit.disabled) return;
            const email = checkoutEmail.value.trim().toLowerCase();
            const plan = selectedCheckoutPlan();
            if (plan !== 'monthly' && plan !== 'annual') {
                showCheckoutError('Choose monthly or annual.');
                return;
            }
            if (!validCheckoutEmail(email)) {
                checkoutEmail.setAttribute('aria-invalid', 'true');
                showCheckoutError('Enter a valid email address.');
                checkoutEmail.focus();
                return;
            }
            checkoutEmail.removeAttribute('aria-invalid');
            startProCheckout(plan, email);
        });
    }

    if (checkoutClose && checkoutDialog) {
        checkoutClose.addEventListener('click', function () {
            checkoutDialog.close();
        });
    }

    if (checkoutDialog) {
        checkoutDialog.addEventListener('close', function () {
            checkoutAttempt += 1;
            setCheckoutBusy(false);
        });
    }

    const portalForm = document.getElementById('portalForm');
    if (portalForm) {
        portalForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const email = document.getElementById('portalEmail').value.trim();
            const box = document.getElementById('portalResult');
            const fallback = 'If that address has a Professional subscription, we sent a link to manage it.';
            try {
                const res = await fetch(API_BASE + '/api/portal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email })
                });
                const data = await res.json();
                box.textContent = data.message || fallback;
            } catch (err) {
                box.textContent = fallback;
            }
            box.className = 'redeem-result visible success';
        });
    }

    // ── Attribution for the Free form ───────────────────────────
    // First touch in this tab. If the URL has a campaign tag, keep it, the
    // external referrer host, and the landing path in sessionStorage. A later
    // page does not overwrite that. Sign-up sends the stored values when the
    // current URL has none. Storage failures are ignored so the form still
    // submits. Only the referring host name is kept, never the full URL.
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
        } catch (err) { /* malformed referrer: leave it empty */ }
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
        } catch (err) { /* storage blocked: sign-up still works */ }
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

    // Tell the API an installer download was started or a link was clicked.
    // sendBeacon with text/plain needs no CORS preflight and survives the
    // page starting a file download. Failure is silent by design.
    function signalConversion(name) {
        try {
            document.dispatchEvent(new CustomEvent('nc-conversion', { detail: { name: name } }));
        } catch (err) { /* the page still works */ }
    }

    function trackDownload(code, platform, kind) {
        if (kind === 'click') signalConversion('download');
        try {
            var tags = funnelCampaign();
            const body = JSON.stringify({
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

    // Anonymous Free-section counts. sendBeacon with text/plain, same as a
    // download event. Failure is silent. View and form start fire once per
    // page load. Submit fires on each submit.
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

    // Helper: show result message in a container
    function showResult(container, message, type) {
        container.className = 'redeem-result visible ' + type;
        if (type === 'success') {
            container.innerHTML = message;
        } else {
            container.textContent = message;
        }
    }

    // Helper: API call wrapper
    async function apiCall(endpoint, data) {
        const res = await fetch(API_BASE + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return { status: res.status, data: await res.json() };
    }

    // ── Free Request Form — Step 1: Request Access ─────────────
    let pendingEmail = '';  // Track email between steps

    const freeForm = document.getElementById('freeRequestForm');
    const verifySection = document.getElementById('verifySection');
    const downloadCodeSection = document.getElementById('downloadCodeSection');
    const reqResult = document.getElementById('reqResult');

    if (freeForm) {
        freeForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            trackFunnel('free_form_submit');

            const btn = document.getElementById('reqSubmitBtn');
            const nameEl = document.getElementById('reqName');
            const name = nameEl ? nameEl.value.trim() : '';
            const email = document.getElementById('reqEmail').value.trim();
            const platform = document.getElementById('reqPlatform').value;
            const company = document.getElementById('reqCompany').value.trim();

            if (!email || !platform) {
                showResult(reqResult, 'Enter your email and platform.', 'error');
                return;
            }

            btn.textContent = 'Sending…';
            btn.style.opacity = '0.6';
            btn.style.pointerEvents = 'none';
            reqResult.className = 'redeem-result';

            try {
                const { status, data } = await apiCall('/api/request-access',
                    Object.assign({ name, email, company, platform }, attributionPayload()));

                if (data.success && data.download_code) {
                    signalConversion('sign_up');
                    pendingEmail = email;
                    freeForm.style.display = 'none';
                    if (verifySection) verifySection.style.display = 'none';
                    downloadCodeSection.style.display = 'block';
                    document.getElementById('revealedCode').textContent = data.download_code;
                    const note = document.getElementById('downloadConfirmNote');
                    if (note) note.style.display = 'block';
                    const redeemInput = document.getElementById('redeemCode');
                    if (redeemInput) {
                        redeemInput.value = data.download_code;
                        setTimeout(() => document.getElementById('redeemBtn').click(), 500);
                    }
                } else if (data.success) {
                    // A page that still has a 6-digit request in progress.
                    pendingEmail = email;
                    freeForm.style.display = 'none';
                    verifySection.style.display = 'block';
                    document.getElementById('verifyEmailDisplay').textContent = email;
                    document.getElementById('verifyCode').focus();
                } else {
                    showResult(reqResult, data.error || 'Something went wrong. Please try again.', 'error');
                    btn.textContent = 'Download Free';
                    btn.style.opacity = '';
                    btn.style.pointerEvents = '';
                }
            } catch (err) {
                showResult(reqResult, 'Connection error. Please try again.', 'error');
                btn.textContent = 'Download Free';
                btn.style.opacity = '';
                btn.style.pointerEvents = '';
            }
        });
    }

    // ── Step 2: Verify email code ──────────────────────────────
    const verifyBtn = document.getElementById('verifyBtn');
    const verifyCodeInput = document.getElementById('verifyCode');
    const verifyResult = document.getElementById('verifyResult');
    const resendBtn = document.getElementById('resendBtn');

    if (verifyBtn) {
        async function doVerify() {
            const code = verifyCodeInput.value.trim();
            if (!code || code.length < 6) {
                showResult(verifyResult, 'Please enter the 6-digit code from your email.', 'error');
                return;
            }

            verifyBtn.textContent = 'Verifying…';
            verifyBtn.style.opacity = '0.6';

            try {
                const { status, data } = await apiCall('/api/verify', { email: pendingEmail, code });

                if (data.success) {
                    // Show the download code
                    verifySection.style.display = 'none';
                    downloadCodeSection.style.display = 'block';
                    document.getElementById('revealedCode').textContent = data.download_code;

                    // Also auto-fill the redeem section
                    const redeemInput = document.getElementById('redeemCode');
                    if (redeemInput) {
                        redeemInput.value = data.download_code;
                        // Auto-trigger redeem
                        setTimeout(() => document.getElementById('redeemBtn').click(), 500);
                    }
                } else {
                    showResult(verifyResult, data.error || 'Invalid code. Please try again.', 'error');
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
        verifyCodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); doVerify(); }
        });
    }

    // Resend button
    if (resendBtn) {
        resendBtn.addEventListener('click', async function () {
            if (!pendingEmail) return;
            this.textContent = 'Resending…';
            this.style.pointerEvents = 'none';

            try {
                // Re-submit the original form data
                const nameEl = document.getElementById('reqName');
                const name = nameEl ? nameEl.value.trim() : '';
                const platform = document.getElementById('reqPlatform').value;
                const company = document.getElementById('reqCompany').value.trim();
                await apiCall('/api/request-access',
                    Object.assign({ name, email: pendingEmail, company, platform }, attributionPayload()));
                this.textContent = 'Code resent! Check your inbox.';
                this.style.color = '#00e8ff';
            } catch (err) {
                this.textContent = 'Failed to resend. Try again.';
            }

            setTimeout(() => {
                this.textContent = "Didn't receive it? Resend code";
                this.style.pointerEvents = '';
                this.style.color = '';
            }, 5000);
        });
    }

    // ── Download Code Redemption (via API) ─────────────────────
    const redeemBtn = document.getElementById('redeemBtn');
    const redeemCode = document.getElementById('redeemCode');
    const redeemResult = document.getElementById('redeemResult');

    if (redeemBtn && redeemCode && redeemResult) {
        // Trigger a file download without leaving the page. GitHub release
        // assets are served as attachments, so navigating a hidden anchor
        // starts the download in place.
        function startDownload(url) {
            const a = document.createElement('a');
            a.href = url;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            setTimeout(() => a.remove(), 1000);
        }

        // A direct installer ends in .dmg or .exe. A signed Free link is
        // /api/v1/download/free/mac or /win and does not. The GitHub
        // releases-page fallback is neither, so it still shows the buttons.
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

        async function validateCode(code) {
            const normalised = code.trim().toUpperCase().replace(/\s+/g, '-');

            if (!normalised) {
                showResult(redeemResult, 'Please enter a download code.', 'error');
                return;
            }

            redeemBtn.textContent = 'Checking…';
            redeemBtn.style.opacity = '0.6';

            try {
                const { status, data } = await apiCall('/api/redeem', { code: normalised });

                if (data.success) {
                    const urls = data.downloads;

                    // Platform chosen in the request form, if the user came
                    // through the email flow this session. Returning users
                    // with a saved code won't have one — treat as "both".
                    const platformSelect = document.getElementById('reqPlatform');
                    const chosen = platformSelect ? platformSelect.value : '';
                    const key = chosen === 'macos' ? 'mac' : chosen === 'windows' ? 'win' : null;

                    if (key && isInstallerUrl(urls[key])) {
                        const other = key === 'mac' ? 'win' : 'mac';
                        const otherLabel = key === 'mac' ? 'Windows (.exe)' : 'macOS (.dmg)';
                        startDownload(urls[key]);
                        trackDownload(normalised, key, 'auto');
                        showResult(redeemResult,
                            '<strong>' + data.label + '</strong> — your download is starting.' +
                            '<div class="redeem-download-links">' +
                            '<a href="' + urls[key] + '" class="redeem-fallback-link" data-platform="' + key + '">Download didn\'t start? Click here.</a>' +
                            '</div>' +
                            '<a href="' + urls[other] + '" class="redeem-other-link" data-platform="' + other + '">Need ' + otherLabel + ' instead?</a>',
                            'success'
                        );
                    } else {
                        showResult(redeemResult,
                            '<strong>' + data.label + '</strong> — choose your platform:' +
                            '<div class="redeem-download-links">' +
                            '<a href="' + urls.mac + '" class="btn btn-outline btn-sm" data-platform="mac">macOS (.dmg)</a>' +
                            '<a href="' + urls.win + '" class="btn btn-outline btn-sm" data-platform="win">Windows (.exe)</a>' +
                            '</div>',
                            'success'
                        );
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

        redeemBtn.addEventListener('click', () => validateCode(redeemCode.value));
        redeemCode.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); validateCode(redeemCode.value); }
        });
    }

    // ── Scroll-triggered fade-in animations ──────────────────
    const animatedElements = document.querySelectorAll(
        '.feature-card, .download-card, .download-tier, .pricing-card, .docs-card, .contact-card, .screenshot-card, .watcher-main-image, .ai-agent-card, .ai-highlight'
    );

    // Reset: hide elements initially until they scroll into view
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.animation = 'none';
    });

    function showElement(el) {
        el.style.opacity = '';
        el.style.animation = '';
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                showElement(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px'
    });

    animatedElements.forEach(el => observer.observe(el));

    // Fallback: if the page loaded with a hash anchor, elements in view
    // may already be intersecting before the observer was created.
    if (window.location.hash) {
        setTimeout(() => {
            animatedElements.forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.top < window.innerHeight && rect.bottom > 0 && el.style.animation === 'none') {
                    showElement(el);
                }
            });
        }, 100);
    }

    // ── Screenshot lightbox ──────────────────────────────────
    // Create lightbox overlay
    const lightbox = document.createElement('div');
    lightbox.className = 'lightbox-overlay';
    lightbox.innerHTML = '<img class="lightbox-img" src="" alt=""><span class="lightbox-close">&times;</span>';
    document.body.appendChild(lightbox);

    const lightboxImg = lightbox.querySelector('.lightbox-img');
    const lightboxClose = lightbox.querySelector('.lightbox-close');

    // Click any screenshot card image to open lightbox
    document.querySelectorAll('.screenshot-card img, .watcher-main-image img').forEach(img => {
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', (e) => {
            e.stopPropagation();
            lightboxImg.src = img.src;
            lightboxImg.alt = img.alt;
            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    });

    function closeLightbox() {
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
    }

    lightbox.addEventListener('click', closeLightbox);
    lightboxClose.addEventListener('click', closeLightbox);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeLightbox();
    });

})();
