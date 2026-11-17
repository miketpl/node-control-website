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
            if (!data || data.free_downloads_paused !== true) return;
            if (downloadSection) downloadSection.classList.add('free-paused');
            document.querySelectorAll('[data-trial-form]').forEach(function (block) {
                block.classList.add('free-paused');
            });
            var notice = document.getElementById('free-paused-notice');
            if (!notice) {
                var header = document.querySelector('#free-edition .download-tier-header');
                if (!header) return;
                notice = document.createElement('p');
                notice.className = 'free-pause-notice';
                notice.id = 'free-paused-notice';
                var hint = header.querySelector('.free-signup-hint');
                if (hint) header.insertBefore(notice, hint);
                else header.appendChild(notice);
            }
            notice.textContent = 'Free downloads are temporarily paused';
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

    // One trial_signup per download code. The dataLayer event is only the
    // name and the method. The code stays in memory and in nc_signup_sent
    // so a repeat response is not sent again. It is not put on the event.
    var signupMemory = {};

    function pushTrialSignup(downloadCode, method) {
        var code = String(downloadCode || '');
        if (!code || signupMemory[code]) return;
        var key = 'nc_signup_sent';
        var sent = [];
        try {
            var stored = JSON.parse(localStorage.getItem(key) || '[]');
            if (Array.isArray(stored)) {
                sent = stored.filter(function (item) {
                    return typeof item === 'string';
                });
            }
        } catch (err) {
            sent = [];
        }
        if (sent.indexOf(code) !== -1) {
            signupMemory[code] = true;
            return;
        }
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event: 'trial_signup', method: method });
        signupMemory[code] = true;
        sent.push(code);
        if (sent.length > 20) sent = sent.slice(sent.length - 20);
        try {
            localStorage.setItem(key, JSON.stringify(sent));
        } catch (err) { /* this page view is already marked in memory */ }
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
        var sections = document.querySelectorAll('[data-trial-view]');
        if (sections.length && typeof IntersectionObserver === 'function') {
            try {
                var observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (seenView || entry.intersectionRatio < 0.5) return;
                        seenView = true;
                        trackFunnel('free_section_view');
                        observer.disconnect();
                    });
                }, { threshold: [0.5] });
                sections.forEach(function (section) { observer.observe(section); });
            } catch (err) { /* leave the page alone */ }
        }
        var forms = document.querySelectorAll('[data-trial-form] form');
        if (!forms.length) return;
        function markStart() {
            if (seenStart) return;
            seenStart = true;
            trackFunnel('free_form_start');
            forms.forEach(function (form) {
                form.removeEventListener('focusin', markStart);
                form.removeEventListener('input', markStart);
            });
        }
        forms.forEach(function (form) {
            form.addEventListener('focusin', markStart);
            form.addEventListener('input', markStart);
        });
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

    // ── Free trial forms. One page can have several. The homepage
    // keeps the original element ids. Other forms use data-trial.
    var TRIAL_LEGACY = {
        email: "reqEmail",
        platform: "reqPlatform",
        company: "reqCompany",
        name: "reqName",
        submit: "reqSubmitBtn",
        result: "reqResult",
        verify: "verifySection",
        "verify-email": "verifyEmailDisplay",
        "verify-code": "verifyCode",
        "verify-btn": "verifyBtn",
        "verify-result": "verifyResult",
        resend: "resendBtn",
        code: "downloadCodeSection",
        revealed: "revealedCode",
        confirm: "downloadConfirmNote",
        "email-note": "downloadEmailNote",
        "email-delivery": "reqEmailDelivery",
        "redeem-code": "redeemCode",
        "redeem-btn": "redeemBtn",
        "redeem-result": "redeemResult"
    };

    function prefersEmailDelivery() {
        try {
            if (window.matchMedia && window.matchMedia("(max-width: 768px)").matches) return true;
        } catch (err) { /* fall through to the user agent */ }
        return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
    }

    function trialNode(root, name) {
        var inside = root.querySelector('[data-trial="' + name + '"]');
        if (inside) return inside;
        if (root.id !== "free-edition") return null;
        var id = TRIAL_LEGACY[name];
        return id ? document.getElementById(id) : null;
    }

    function startDownload(url) {
        var a = document.createElement("a");
        a.href = url;
        a.style.display = "none";
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

    function bindTrialForm(root) {
        var form = root.querySelector("form");
        var emailInput = trialNode(root, "email");
        var platformSelect = trialNode(root, "platform");
        var companyInput = trialNode(root, "company");
        var nameInput = trialNode(root, "name");
        var submitBtn = trialNode(root, "submit");
        var reqResult = trialNode(root, "result");
        var verifySection = trialNode(root, "verify");
        var verifyEmail = trialNode(root, "verify-email");
        var verifyCodeInput = trialNode(root, "verify-code");
        var verifyBtn = trialNode(root, "verify-btn");
        var verifyResult = trialNode(root, "verify-result");
        var resendBtn = trialNode(root, "resend");
        var codeSection = trialNode(root, "code");
        var revealed = trialNode(root, "revealed");
        var confirmNote = trialNode(root, "confirm");
        var emailNote = trialNode(root, "email-note");
        var emailDelivery = trialNode(root, "email-delivery");
        var emailDeliveryNote = root.querySelector("[data-trial='email-note-preview']");
        var redeemCode = trialNode(root, "redeem-code");
        var redeemBtn = trialNode(root, "redeem-btn");
        var redeemResult = trialNode(root, "redeem-result");
        var pendingEmail = "";

        function wantsEmail() {
            return !!(emailDelivery && emailDelivery.checked);
        }

        function idleLabel() {
            if (wantsEmail()) return "Email me the download";
            return (submitBtn && submitBtn.getAttribute("data-label")) || "Start the 14-day trial";
        }

        function restoreSubmit() {
            if (!submitBtn) return;
            submitBtn.textContent = idleLabel();
            submitBtn.style.opacity = "";
            submitBtn.style.pointerEvents = "";
        }

        function syncEmailDelivery() {
            if (emailDeliveryNote) emailDeliveryNote.hidden = !wantsEmail();
            if (wantsEmail() && platformSelect && !platformSelect.value) platformSelect.value = "both";
            if (submitBtn && submitBtn.style.pointerEvents !== "none") submitBtn.textContent = idleLabel();
        }

        if (emailDelivery) {
            if (prefersEmailDelivery()) emailDelivery.checked = true;
            emailDelivery.addEventListener("change", syncEmailDelivery);
            syncEmailDelivery();
        }

        function reveal(el) {
            if (!el) return;
            el.hidden = false;
            el.style.display = "block";
        }

        function showCode(code) {
            if (form) form.style.display = "none";
            if (verifySection) verifySection.style.display = "none";
            reveal(codeSection);
            if (revealed) revealed.textContent = code;
            if (confirmNote) confirmNote.style.display = "block";
            if (emailNote) {
                emailNote.hidden = false;
                emailNote.style.display = wantsEmail() ? "block" : "none";
            }
            if (!wantsEmail() && redeemCode && redeemBtn) {
                redeemCode.value = code;
                setTimeout(function () { redeemBtn.click(); }, 500);
            }
        }

        if (form && emailInput && platformSelect && submitBtn && reqResult) {
            form.addEventListener("submit", async function (e) {
                e.preventDefault();
                trackFunnel("free_form_submit");
                var name = nameInput ? nameInput.value.trim() : "";
                var email = emailInput.value.trim();
                var platform = platformSelect.value;
                var company = companyInput ? companyInput.value.trim() : "";
                if (!email || !platform) {
                    showResult(reqResult, "Enter your email and platform.", "error");
                    return;
                }
                submitBtn.textContent = "Sending…";
                submitBtn.style.opacity = "0.6";
                submitBtn.style.pointerEvents = "none";
                reqResult.className = "redeem-result";
                try {
                    var result = await apiCall("/api/request-access",
                        Object.assign({ name: name, email: email, company: company, platform: platform }, attributionPayload()));
                    var data = result.data;
                    if (data.success && data.download_code) {
                        signalConversion("sign_up");
                        pushTrialSignup(data.download_code, "request_access");
                        pendingEmail = email;
                        showCode(data.download_code);
                    } else if (data.success && verifySection && verifyEmail && verifyCodeInput) {
                        pendingEmail = email;
                        form.style.display = "none";
                        reveal(verifySection);
                        verifyEmail.textContent = email;
                        verifyCodeInput.focus();
                    } else {
                        showResult(reqResult, data.error || "Something went wrong. Please try again.", "error");
                        restoreSubmit();
                    }
                } catch (err) {
                    showResult(reqResult, "Connection error. Please try again.", "error");
                    restoreSubmit();
                }
            });
        }

        if (verifyBtn && verifyCodeInput && verifyResult && verifySection && codeSection) {
            async function doVerify() {
                var code = verifyCodeInput.value.trim();
                if (!code || code.length < 6) {
                    showResult(verifyResult, "Please enter the 6-digit code from your email.", "error");
                    return;
                }
                verifyBtn.textContent = "Verifying…";
                verifyBtn.style.opacity = "0.6";
                try {
                    var result = await apiCall("/api/verify", { email: pendingEmail, code: code });
                    if (result.data.success && result.data.download_code) {
                        pushTrialSignup(result.data.download_code, "verify");
                        showCode(result.data.download_code);
                    } else {
                        showResult(verifyResult, result.data.error || "Invalid code. Please try again.", "error");
                        verifyBtn.textContent = "Verify";
                        verifyBtn.style.opacity = "";
                    }
                } catch (err) {
                    showResult(verifyResult, "Connection error. Please try again.", "error");
                    verifyBtn.textContent = "Verify";
                    verifyBtn.style.opacity = "";
                }
            }
            verifyBtn.addEventListener("click", doVerify);
            verifyCodeInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") { e.preventDefault(); doVerify(); }
            });
        }

        if (resendBtn) {
            resendBtn.addEventListener("click", async function () {
                if (!pendingEmail) return;
                this.textContent = "Resending…";
                this.style.pointerEvents = "none";
                try {
                    var name = nameInput ? nameInput.value.trim() : "";
                    var platform = platformSelect ? platformSelect.value : "";
                    var company = companyInput ? companyInput.value.trim() : "";
                    await apiCall("/api/request-access",
                        Object.assign({ name: name, email: pendingEmail, company: company, platform: platform }, attributionPayload()));
                    this.textContent = "Code resent. Check your inbox.";
                    this.style.color = "#00e8ff";
                } catch (err) {
                    this.textContent = "Failed to resend. Try again.";
                }
                var button = this;
                setTimeout(function () {
                    button.textContent = "Didn't receive it? Resend code";
                    button.style.pointerEvents = "";
                    button.style.color = "";
                }, 5000);
            });
        }

        if (redeemBtn && redeemCode && redeemResult) {
            async function validateCode(code) {
                var normalised = code.trim().toUpperCase().replace(/\s+/g, "-");
                if (!normalised) {
                    showResult(redeemResult, "Please enter a download code.", "error");
                    return;
                }
                redeemBtn.textContent = "Checking…";
                redeemBtn.style.opacity = "0.6";
                try {
                    var result = await apiCall("/api/redeem", { code: normalised });
                    var data = result.data;
                    if (data.success) {
                        var urls = data.downloads;
                        var chosen = platformSelect ? platformSelect.value : "";
                        var key = chosen === "macos" ? "mac" : chosen === "windows" ? "win" : null;
                        if (key && isInstallerUrl(urls[key])) {
                            var other = key === "mac" ? "win" : "mac";
                            var otherLabel = key === "mac" ? "Windows (.exe)" : "macOS (.dmg)";
                            startDownload(urls[key]);
                            trackDownload(normalised, key, "auto");
                            showResult(redeemResult,
                                "<strong>" + data.label + "</strong> — your download is starting." +
                                '<div class="redeem-download-links">' +
                                '<a href="' + urls[key] + '" class="redeem-fallback-link" data-platform="' + key + '">Download didn\'t start? Click here.</a>' +
                                "</div>" +
                                '<a href="' + urls[other] + '" class="redeem-other-link" data-platform="' + other + '">Need ' + otherLabel + " instead?</a>",
                                "success");
                        } else {
                            showResult(redeemResult,
                                "<strong>" + data.label + "</strong> — choose your platform:" +
                                '<div class="redeem-download-links">' +
                                '<a href="' + urls.mac + '" class="btn btn-outline btn-sm" data-platform="mac">macOS (.dmg)</a>' +
                                '<a href="' + urls.win + '" class="btn btn-outline btn-sm" data-platform="win">Windows (.exe)</a>' +
                                "</div>",
                                "success");
                        }
                        redeemResult.querySelectorAll("a[data-platform]").forEach(function (link) {
                            link.addEventListener("click", function () {
                                trackDownload(normalised, link.getAttribute("data-platform"), "click");
                            });
                        });
                    } else {
                        showResult(redeemResult, data.error || "Invalid code. Please try again.", "error");
                    }
                } catch (err) {
                    showResult(redeemResult, "Connection error. Please try again.", "error");
                }
                redeemBtn.textContent = "Redeem";
                redeemBtn.style.opacity = "";
            }
            redeemBtn.addEventListener("click", function () { validateCode(redeemCode.value); });
            redeemCode.addEventListener("keydown", function (e) {
                if (e.key === "Enter") { e.preventDefault(); validateCode(redeemCode.value); }
            });
        }
    }

    document.querySelectorAll("[data-trial-form]").forEach(bindTrialForm);

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
