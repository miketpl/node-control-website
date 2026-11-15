/* Cookie banner and Consent Mode updates. The default deny call stays inline
   in each page, ahead of the Google Tag Manager snippet. This file applies a
   saved choice and draws the banner. */
(function () {
    'use strict';

    var STORAGE_KEY = 'nc_cookie_consent';

    function gtag() {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push(arguments);
    }

    function ensureGtag() {
        if (typeof window.gtag !== 'function') window.gtag = gtag;
    }

    function readChoice() {
        try {
            var data = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (!data || typeof data.ads !== 'boolean' || typeof data.analytics !== 'boolean') return null;
            return { ads: data.ads, analytics: data.analytics };
        } catch (err) {
            return null;
        }
    }

    function writeChoice(choice) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                ads: !!choice.ads,
                analytics: !!choice.analytics
            }));
        } catch (err) { /* the update below still applies to this page */ }
    }

    function applyChoice(choice) {
        ensureGtag();
        var ads = choice.ads ? 'granted' : 'denied';
        var analytics = choice.analytics ? 'granted' : 'denied';
        window.gtag('consent', 'update', {
            ad_storage: ads,
            ad_user_data: ads,
            ad_personalization: ads,
            analytics_storage: analytics,
            functionality_storage: 'denied',
            personalization_storage: 'denied',
            security_storage: 'granted'
        });
    }

    var saved = readChoice();
    if (saved) applyChoice(saved);

    function removeBanner() {
        var banner = document.getElementById('nc-consent');
        if (banner) banner.remove();
        document.documentElement.classList.remove('nc-consent-open');
    }

    function choose(choice) {
        writeChoice(choice);
        applyChoice(choice);
        removeBanner();
    }

    function showBanner(openManage) {
        var current = document.getElementById('nc-consent');
        if (current) current.remove();

        var stored = readChoice();
        var banner = document.createElement('div');
        banner.id = 'nc-consent';
        banner.className = 'nc-consent';
        banner.setAttribute('role', 'region');
        banner.setAttribute('aria-labelledby', 'nc-consent-title');
        banner.innerHTML = ''
            + '<div class="nc-consent-inner">'
            + '<div class="nc-consent-copy">'
            + '<p id="nc-consent-title">Cookies</p>'
            + '<p>Analytics and ads cookies stay off until you choose. Analytics measures visits. Ads measures whether an ad led to a purchase. '
            + '<a href="/privacy.html#cookies">Privacy</a>.</p>'
            + '</div>'
            + '<div class="nc-consent-actions">'
            + '<button type="button" class="nc-consent-choice" id="nc-consent-reject">Reject all</button>'
            + '<button type="button" class="nc-consent-choice" id="nc-consent-accept">Accept all</button>'
            + '<button type="button" class="nc-consent-manage" id="nc-consent-manage" aria-expanded="false" aria-controls="nc-consent-panel">Manage</button>'
            + '</div>'
            + '<div class="nc-consent-panel" id="nc-consent-panel" hidden>'
            + '<label for="nc-consent-analytics"><input type="checkbox" id="nc-consent-analytics"> Analytics</label>'
            + '<label for="nc-consent-ads"><input type="checkbox" id="nc-consent-ads"> Ads</label>'
            + '<button type="button" class="nc-consent-choice" id="nc-consent-save">Save choices</button>'
            + '</div>'
            + '</div>';
        document.body.appendChild(banner);
        document.documentElement.classList.add('nc-consent-open');

        var analyticsInput = document.getElementById('nc-consent-analytics');
        var adsInput = document.getElementById('nc-consent-ads');
        var panel = document.getElementById('nc-consent-panel');
        var manageButton = document.getElementById('nc-consent-manage');

        function setPanel(open) {
            panel.hidden = !open;
            manageButton.setAttribute('aria-expanded', open ? 'true' : 'false');
            document.documentElement.classList.toggle('nc-consent-manage-open', open);
        }

        if (openManage) {
            if (stored) {
                analyticsInput.checked = stored.analytics;
                adsInput.checked = stored.ads;
            }
            setPanel(true);
        }

        document.getElementById('nc-consent-reject').addEventListener('click', function () {
            choose({ ads: false, analytics: false });
        });
        document.getElementById('nc-consent-accept').addEventListener('click', function () {
            choose({ ads: true, analytics: true });
        });
        manageButton.addEventListener('click', function () {
            var open = panel.hidden;
            setPanel(open);
            if (open) analyticsInput.focus();
        });
        document.getElementById('nc-consent-save').addEventListener('click', function () {
            choose({ ads: adsInput.checked, analytics: analyticsInput.checked });
        });
    }

    function boot() {
        if (!readChoice()) showBanner(false);
        document.addEventListener('click', function (event) {
            var link = event.target && event.target.closest && event.target.closest('a.nc-cookie-settings');
            if (!link) return;
            event.preventDefault();
            showBanner(true);
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
}());
