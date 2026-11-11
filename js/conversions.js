/* Paid-ad conversions. Off unless NC_ADS.enabled is true.
   While it is false this file does not read storage, does not add a banner,
   and does not request anything from Reddit or Google.
   Turn it on only together with the draft wording in drafts/paid-ads-privacy.md.
   The ids below are placeholders. Replace them before enabling. */
(function () {
    'use strict';

    var NC_ADS = {
        enabled: false,
        redditPixelId: 'REDDIT_PIXEL_ID',
        googleAdsId: 'AW-GOOGLE_ADS_ID',
        googleSignUpLabel: 'GOOGLE_SIGNUP_LABEL',
        googleDownloadLabel: 'GOOGLE_DOWNLOAD_LABEL'
    };

    var CONSENT_KEY = 'nc_ads_consent';

    function readConsent() {
        try {
            return localStorage.getItem(CONSENT_KEY);
        } catch (err) {
            return null;
        }
    }

    function writeConsent(value) {
        try {
            localStorage.setItem(CONSENT_KEY, value);
        } catch (err) { /* the choice still applies for this page view */ }
    }

    function loadPixels() {
        if (window.__ncAdsLoaded) return;
        window.__ncAdsLoaded = true;

        window.rdt = window.rdt || function () {
            if (window.rdt.sendEvent) window.rdt.sendEvent.apply(window.rdt, arguments);
            else window.rdt.callQueue.push(arguments);
        };
        window.rdt.callQueue = window.rdt.callQueue || [];

        var reddit = document.createElement('script');
        reddit.async = true;
        reddit.src = 'https://www.redditstatic.com/ads/pixel.js';
        document.head.appendChild(reddit);
        window.rdt('init', NC_ADS.redditPixelId);

        window.dataLayer = window.dataLayer || [];
        window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
        var google = document.createElement('script');
        google.async = true;
        google.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(NC_ADS.googleAdsId);
        document.head.appendChild(google);
        window.gtag('js', new Date());
        window.gtag('config', NC_ADS.googleAdsId);
    }

    function fire(name) {
        if (readConsent() !== 'accept') return;
        loadPixels();
        if (name === 'sign_up') {
            window.rdt('track', 'SignUp');
            window.gtag('event', 'conversion', {
                send_to: NC_ADS.googleAdsId + '/' + NC_ADS.googleSignUpLabel
            });
        } else if (name === 'download') {
            window.rdt('track', 'Custom', { customEventName: 'Download' });
            window.gtag('event', 'conversion', {
                send_to: NC_ADS.googleAdsId + '/' + NC_ADS.googleDownloadLabel
            });
        }
    }

    function banner() {
        if (document.getElementById('nc-consent')) return;
        var box = document.createElement('div');
        box.id = 'nc-consent';
        box.className = 'nc-consent';
        box.setAttribute('role', 'region');
        box.setAttribute('aria-label', 'Advertising measurement');
        box.innerHTML = ''
            + '<p id="nc-consent-title">Allow advertising measurement?</p>'
            + '<p>Nothing is sent until you accept. Accept tells Reddit and Google that a Free sign-up or a Free download happened. Reject sends nothing. The choice is remembered in this browser. It is not a cookie.</p>'
            + '<div class="nc-consent-actions">'
            + '<button type="button" id="nc-consent-reject">Reject</button>'
            + '<button type="button" id="nc-consent-accept">Accept</button>'
            + '</div>';
        document.body.appendChild(box);
        document.getElementById('nc-consent-reject').addEventListener('click', function () {
            writeConsent('reject');
            box.remove();
        });
        document.getElementById('nc-consent-accept').addEventListener('click', function () {
            writeConsent('accept');
            box.remove();
            loadPixels();
        });
    }

    function boot() {
        if (!NC_ADS.enabled) return;
        var choice = readConsent();
        if (choice === 'accept') loadPixels();
        else if (choice !== 'reject') {
            if (document.body) banner();
            else document.addEventListener('DOMContentLoaded', banner);
        }
        document.addEventListener('nc-conversion', function (event) {
            var name = event && event.detail && event.detail.name;
            if (name === 'sign_up' || name === 'download') fire(name);
        });
    }

    boot();
}());
