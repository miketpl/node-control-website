# Draft — not linked from the site

This wording is for `privacy.html` only after `NC_ADS.enabled` in `js/conversions.js` is set to true and the placeholder ids are replaced. Do not publish it while the flag is false. The live privacy page does not mention these tags.

## Advertising measurement

If you accept on the banner, the site loads the Reddit Pixel and the Google Ads tag. Until you accept, neither script is requested. Reject stores that choice and sends nothing. The choice is kept in the browser's local storage under the key `nc_ads_consent`. It is not a cookie. The banner is not shown again after you choose.

After you accept, two events can be sent:

- `sign_up`, when the Free form is accepted by the server
- `download`, when you click a Free installer link

The event says that a sign-up or a download happened. It does not include your name, email, company, or download code. Reddit and Google also receive the usual data a script on the page can see, including the IP address of the connection and the advertising click id those companies set in a cookie after you accept. Those cookies are theirs. This site does not read them.

The lawful basis for this measurement is consent. You can reject, and you can clear the saved choice by removing `nc_ads_consent` from local storage for nodecontrol.io. The site then asks again on the next visit, and nothing is sent until you accept.

Reddit's pixel is served from `www.redditstatic.com`. Google's tag is served from `www.googletagmanager.com`. Both may process the event outside the United Kingdom. The international-transfers paragraph on the privacy page already covers processors of that kind.
