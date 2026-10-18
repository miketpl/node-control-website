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

    // SINGLE SWITCH. Pro checkout stays off until it is turned on.
    // true: show .pro-checkout, hide .pro-waitlist, and point the hero button at pricing.
    // false: class "payment-pending" keeps the subscribe buttons hidden.
    const PRO_CHECKOUT_LIVE = false;

    function selectedProPlan() {
        const checked = document.querySelector('input[name="proPlan"]:checked');
        return checked ? checked.value : 'monthly';
    }

    function renderProPrice() {
        const price = document.getElementById('proPriceDisplay');
        const note = document.getElementById('proPriceNote');
        if (!price || !note) return;
        if (selectedProPlan() === 'annual') {
            price.innerHTML = '£21.25<span>/mo ex VAT</span>';
            note.textContent = '£21.25/mo billed annually, ex VAT. £255/year ex VAT. Save 15%.';
        } else {
            price.innerHTML = '£25<span>/month ex VAT</span>';
            note.textContent = 'Or £255/year ex VAT (£21.25/mo billed annually, ex VAT, save 15%).';
        }
    }

    document.querySelectorAll('input[name="proPlan"]').forEach(function (input) {
        input.addEventListener('change', renderProPrice);
    });
    renderProPrice();

    if (PRO_CHECKOUT_LIVE) {
        document.querySelectorAll('.pro-checkout').forEach(function (el) {
            el.classList.remove('payment-pending');
        });
        document.querySelectorAll('.pro-waitlist').forEach(function (el) {
            el.hidden = true;
        });
        const hero = document.querySelector('.hero-buttons a.btn-primary');
        if (hero) {
            hero.textContent = 'Subscribe to Pro';
            hero.setAttribute('href', '#pricing');
        }
    }

    async function startProCheckout(plan) {
        const result = document.getElementById('proCheckoutResult');
        try {
            const res = await fetch(API_BASE + '/api/checkout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ plan: plan })
            });
            const data = await res.json();
            if (!res.ok || !data.url) {
                throw new Error('checkout failed');
            }
            window.location.href = data.url;
        } catch (err) {
            if (result) {
                result.textContent = 'Checkout could not be started. Try again, or use the waitlist.';
                result.className = 'redeem-result visible error';
            }
        }
    }

    document.querySelectorAll('[data-pro-checkout]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            if (!PRO_CHECKOUT_LIVE) return;
            startProCheckout(selectedProPlan());
        });
    });

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

            const btn = document.getElementById('reqSubmitBtn');
            const name = document.getElementById('reqName').value.trim();
            const email = document.getElementById('reqEmail').value.trim();
            const platform = document.getElementById('reqPlatform').value;
            const company = document.getElementById('reqCompany').value.trim();

            if (!name || !email || !platform) {
                showResult(reqResult, 'Please fill in all required fields.', 'error');
                return;
            }

            btn.textContent = 'Sending…';
            btn.style.opacity = '0.6';
            btn.style.pointerEvents = 'none';
            reqResult.className = 'redeem-result';

            try {
                const { status, data } = await apiCall('/api/request-access', { name, email, company, platform });

                if (data.success) {
                    // Show verification step
                    pendingEmail = email;
                    freeForm.style.display = 'none';
                    verifySection.style.display = 'block';
                    document.getElementById('verifyEmailDisplay').textContent = email;
                    document.getElementById('verifyCode').focus();
                } else {
                    showResult(reqResult, data.error || 'Something went wrong. Please try again.', 'error');
                    btn.textContent = 'Request Free Access';
                    btn.style.opacity = '';
                    btn.style.pointerEvents = '';
                }
            } catch (err) {
                showResult(reqResult, 'Connection error. Please try again.', 'error');
                btn.textContent = 'Request Free Access';
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
                const name = document.getElementById('reqName').value.trim();
                const platform = document.getElementById('reqPlatform').value;
                const company = document.getElementById('reqCompany').value.trim();
                await apiCall('/api/request-access', { name, email: pendingEmail, company, platform });
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

        // True only for a direct installer URL — not the releases-page
        // fallback the backend returns when it can't resolve assets.
        function isInstallerUrl(url) {
            return /\.(dmg|exe)$/i.test(url || '');
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
                        showResult(redeemResult,
                            '<strong>' + data.label + '</strong> — your download is starting.' +
                            '<div class="redeem-download-links">' +
                            '<a href="' + urls[key] + '" class="redeem-fallback-link">Download didn\'t start? Click here.</a>' +
                            '</div>' +
                            '<a href="' + urls[other] + '" class="redeem-other-link">Need ' + otherLabel + ' instead?</a>',
                            'success'
                        );
                    } else {
                        showResult(redeemResult,
                            '<strong>' + data.label + '</strong> — choose your platform:' +
                            '<div class="redeem-download-links">' +
                            '<a href="' + urls.mac + '" class="btn btn-outline btn-sm">macOS (.dmg)</a>' +
                            '<a href="' + urls.win + '" class="btn btn-outline btn-sm">Windows (.exe)</a>' +
                            '</div>',
                            'success'
                        );
                    }
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
