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
		const u = "//samim.io/MatomoStats/";
		_paq.push(["setTrackerUrl", u + "hokuspokusp"]);
		_paq.push(["setSiteId", "1"]);
		const d = document,
			g = d.createElement("script"),
			s = d.getElementsByTagName("script")[0];
		g.type = "text/javascript";
		g.async = true;
		g.defer = true;
		g.src = u + "hokuspokusj";
		s.parentNode.insertBefore(g, s);
	})();
}
