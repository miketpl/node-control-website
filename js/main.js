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

    // ── Scroll-triggered fade-in animations ──────────────────
    const animatedElements = document.querySelectorAll(
        '.feature-card, .download-card, .pricing-card, .docs-card, .contact-card'
    );

    // Reset: hide elements initially until they scroll into view
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.animation = 'none';
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                // Restore the CSS animation
                el.style.animation = '';
                observer.unobserve(el);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px'
    });

    animatedElements.forEach(el => observer.observe(el));

    // ── Screenshot category tabs ───────────────────────────
    const tabs = document.querySelectorAll('.screenshot-tab');
    const categories = document.querySelectorAll('.screenshot-category');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const cat = tab.dataset.category;
            tabs.forEach(t => t.classList.remove('active'));
            categories.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = document.querySelector(`.screenshot-category[data-category="${cat}"]`);
            if (target) {
                target.classList.add('active');
                // Re-trigger fade-in for newly visible cards
                target.querySelectorAll('.screenshot-card').forEach(card => {
                    card.style.opacity = '1';
                    card.style.animation = 'fadeInUp 0.5s ease forwards';
                });
            }
        });
    });

})();

// ── Lightbox (global scope for onclick) ────────────────────
function openLightbox(card) {
    const img = card.querySelector('img');
    const overlay = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    if (img && overlay && lightboxImg) {
        lightboxImg.src = img.src;
        lightboxImg.alt = img.alt;
        overlay.classList.add('active');
    }
}

function closeLightbox() {
    const overlay = document.getElementById('lightbox');
    if (overlay) overlay.classList.remove('active');
}

// Close lightbox on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
});
