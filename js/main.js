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

    // ── Stripe Payment Link handling for paid downloads ──────
    // When a paid download button is clicked, redirect to Stripe first.
    // After payment, Stripe redirects back with ?session_id= and the
    // download starts automatically.
    //
    // SETUP: Replace STRIPE_PRO_LINK and STRIPE_AI_LINK with your
    // actual Stripe Payment Link URLs from the Stripe Dashboard.
    // e.g. https://buy.stripe.com/live_xxxxxxxxxxxx
    //
    // Stripe Payment Links are the simplest approach — no backend needed.
    // Create them at: https://dashboard.stripe.com/payment-links
    //
    // Flow:
    // 1. User clicks "Subscribe & Download" on pricing or "Download" on Pro tier
    // 2. JS intercepts click, redirects to Stripe Payment Link
    // 3. After payment, Stripe redirects to your success URL
    // 4. Success page triggers the GitHub release download
    //
    document.querySelectorAll('[data-stripe-link]').forEach(btn => {
        btn.addEventListener('click', function (e) {
            const stripeLink = this.dataset.stripeLink;
            // If the Stripe link is still a placeholder, let the normal href work
            if (!stripeLink || stripeLink.startsWith('STRIPE_')) return;

            e.preventDefault();
            // Redirect to Stripe Checkout — pass the download URL as metadata
            const downloadUrl = this.getAttribute('href');
            const returnUrl = window.location.origin + window.location.pathname
                + '?download=' + encodeURIComponent(downloadUrl) + '&paid=true';
            window.location.href = stripeLink + '?client_reference_id=pro&success_url=' + encodeURIComponent(returnUrl);
        });
    });

    // Auto-trigger download after successful Stripe payment redirect
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('paid') === 'true' && urlParams.get('download')) {
        const downloadUrl = decodeURIComponent(urlParams.get('download'));
        // Small delay to let the page load, then trigger download
        setTimeout(() => {
            window.location.href = downloadUrl;
            // Clean up the URL
            window.history.replaceState({}, '', window.location.pathname + '#download');
        }, 1500);
    }

    // ── License API Configuration ────────────────────────────────
    // Change this to your VPS URL in production
    const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:5000'
        : 'https://api.nodecontrol.io';  // Update to your API domain

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
                    showResult(redeemResult,
                        '<strong>' + data.label + '</strong> — choose your platform:' +
                        '<div class="redeem-download-links">' +
                        '<a href="' + urls.mac + '" class="btn btn-outline btn-sm">macOS (.dmg)</a>' +
                        '<a href="' + urls.win + '" class="btn btn-outline btn-sm">Windows (.exe)</a>' +
                        '</div>',
                        'success'
                    );
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
