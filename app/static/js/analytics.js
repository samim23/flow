// analytics.js

var _paq = window._paq || [];

if (
	window.location.href.includes("localhost") ||
	window.location.href.includes("127.0.0.1")
) {
	console.log("flow", window.location.href);
} else {
	_paq.push(["setDocumentTitle", document.title]);
	_paq.push(["trackPageView"]);
	_paq.push(["enableHeartBeatTimer"]);
	_paq.push(["enableLinkTracking"]);

	(function () {
		// insert your analytics code here
	})();
}
