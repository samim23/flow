// Global state
let scrollend = false;
let loading = false;
let currentPage = 0;

// Use existing editing variable if it exists, otherwise don't declare it
// This avoids conflicts with other scripts
if (typeof editing === "undefined") {
	window.editing = false;
}

// Utility functions
function isMobile() {
	const mobileRegex =
		/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|ipad|iris|kindle|Android|Silk|lge |maemo|midp|mmp|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i;
	const mobilePrefixRegex =
		/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i;
	return (
		mobileRegex.test(navigator.userAgent) ||
		mobilePrefixRegex.test(navigator.userAgent.substr(0, 4))
	);
}

function isBot() {
	const botPattern =
		"(googlebot/|bot|Googlebot-Mobile|Googlebot-Image|Google favicon|Mediapartners-Google|bingbot|slurp|java|wget|curl|Commons-HttpClient|Python-urllib|libwww|httpunit|nutch|phpcrawl|msnbot|jyxobot|FAST-WebCrawler|FAST Enterprise Crawler|biglotron|teoma|convera|seekbot|gigablast|exabot|ngbot|ia_archiver|GingerCrawler|webmon |httrack|webcrawler|grub.org|UsineNouvelleCrawler|antibot|netresearchserver|speedy|fluffy|bibnum.bnf|findlink|msrbot|panscient|yacybot|AISearchBot|IOI|ips-agent|tagoobot|MJ12bot|dotbot|woriobot|yanga|buzzbot|mlbot|yandexbot|purebot|Linguee Bot|Voyager|CyberPatrol|voilabot|baiduspider|citeseerxbot|spbot|twengabot|postrank|turnitinbot|scribdbot|page2rss|sitebot|linkdex|Adidxbot|blekkobot|ezooms|dotbot|Mail.RU_Bot|discobot|heritrix|findthatfile|europarchive.org|NerdByNature.Bot|sistrix crawler|ahrefsbot|Aboundex|domaincrawler|wbsearchbot|summify|ccbot|edisterbot|seznambot|ec2linkfinder|gslfbot|aihitbot|intelium_bot|facebookexternalhit|yeti|RetrevoPageAnalyzer|lb-spider|sogou|lssbot|careerbot|wotbox|wocbot|ichiro|DuckDuckBot|lssrocketcrawler|drupact|webcompanycrawler|acoonbot|openindexspider|gnam gnam spider|web-archive-net.com.bot|backlinkcrawler|coccoc|integromedb|content crawler spider|toplistbot|seokicks-robot|it2media-domain-crawler|ip-web-crawler.com|siteexplorer.info|elisabot|proximic|changedetection|blexbot|arabot|WeSEE:Search|niki-bot|CrystalSemanticsBot|rogerbot|360Spider|psbot|InterfaxScanBot|CC Metadata Scaper)";
	const re = new RegExp(botPattern, "i");
	return re.test(navigator.userAgent);
}

// Image Gallery class
class ImageGallery {
	constructor() {
		this.modalContainer = null;
		this.currentIndex = 0;
		this.images = [];
		this.initModal();
	}

	initModal() {
		// Remove any existing modal containers first
		const existingModal = document.querySelector(".image-modal");
		if (existingModal) {
			existingModal.remove();
		}

		this.modalContainer = document.createElement("div");
		this.modalContainer.className = "image-modal";
		this.modalContainer.style.cssText = `
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1002;
            justify-content: center;
            align-items: center;
        `;

		// Add navigation buttons
		const prevButton = document.createElement("button");
		prevButton.textContent = "←";
		prevButton.className = "gallery-nav prev";
		prevButton.onclick = () => this.navigate(-1);

		const nextButton = document.createElement("button");
		nextButton.textContent = "→";
		nextButton.className = "gallery-nav next";
		nextButton.onclick = () => this.navigate(1);

		const closeButton = document.createElement("button");
		closeButton.textContent = "×";
		closeButton.className = "gallery-close";
		closeButton.onclick = () => this.hide();

		this.modalContainer.appendChild(prevButton);
		this.modalContainer.appendChild(nextButton);
		this.modalContainer.appendChild(closeButton);

		const imageContainer = document.createElement("div");
		imageContainer.className = "gallery-image-container";

		// Prevent clicks on the image from closing the gallery
		imageContainer.addEventListener("click", (e) => {
			if (e.target.tagName === "IMG") {
				e.stopPropagation();
			}
		});

		this.modalContainer.appendChild(imageContainer);

		// Close when clicking anywhere in the modal except the image or navigation
		this.modalContainer.addEventListener("click", (e) => {
			if (
				e.target.tagName !== "IMG" &&
				!e.target.classList.contains("gallery-nav") &&
				!e.target.classList.contains("gallery-close")
			) {
				this.hide();
			}
		});

		document.body.appendChild(this.modalContainer);

		// Add keyboard navigation
		document.addEventListener("keydown", (e) => {
			if (this.modalContainer.style.display === "flex") {
				if (e.key === "ArrowLeft") this.navigate(-1);
				if (e.key === "ArrowRight") this.navigate(1);
				if (e.key === "Escape") this.hide();
			}
		});
	}

	show(images, startIndex = 0) {
		if (editing) return;
		this.images = images;
		this.currentIndex = startIndex;
		this.updateImage();
		this.modalContainer.style.display = "flex";
	}

	hide() {
		this.modalContainer.style.display = "none";
		// Clean up the container's contents
		const imageContainer = this.modalContainer.querySelector(
			".gallery-image-container"
		);
		if (imageContainer) {
			imageContainer.innerHTML = "";
		}
	}

	navigate(direction) {
		this.currentIndex =
			(this.currentIndex + direction + this.images.length) % this.images.length;
		this.updateImage();
	}

	updateImage() {
		const container = this.modalContainer.querySelector(
			".gallery-image-container"
		);
		container.innerHTML = "";
		const img = document.createElement("img");
		img.src = this.images[this.currentIndex];
		img.style.cssText =
			"max-width: 90%; max-height: 90vh; object-fit: contain;";
		container.appendChild(img);
	}
}

// Gallery will be initialized after DOM is ready
let gallery;

function getRelativeTimeString(date) {
	const now = new Date();
	const diff = now - new Date(date);
	const seconds = Math.floor(diff / 1000);
	const minutes = Math.floor(seconds / 60);
	const hours = Math.floor(minutes / 60);
	const days = Math.floor(hours / 24);
	const months = Math.floor(days / 30);
	const years = Math.floor(days / 365);

	if (seconds < 60) return "just now";
	if (minutes === 1) return "a minute ago";
	if (minutes < 60) return `${minutes} minutes ago`;
	if (hours === 1) return "an hour ago";
	if (hours < 24) return `${hours} hours ago`;
	if (days === 1) return "a day ago";
	if (days < 30) return `${days} days ago`;
	if (months === 1) return "a month ago";
	if (months < 12) return `${months} months ago`;
	if (years === 1) return "a year ago";
	return `${years} years ago`;
}

function formatDate() {
	if (!isBot()) {
		document.querySelectorAll(".post_date_title").forEach((el) => {
			el.style.display = "none";
		});
	}

	document
		.querySelectorAll(".dt-published:not([data-formatted])")
		.forEach((dateElem) => {
			const date = dateElem.getAttribute("datetime");
			const formatted = getRelativeTimeString(date);
			dateElem.textContent = formatted;
			dateElem.setAttribute("data-formatted", "true");
		});
}

function formatContentHeight(element) {
	if (
		!element.classList.contains("content_shortend") &&
		!element.classList.contains("content_open")
	) {
		element.classList.add("content_open");
		const images = element.querySelectorAll("img");

		if (element.offsetHeight > 640 || images.length > 10) {
			element.classList.add("content_shortend");
			const initialHeight = element.offsetHeight + "px";
			element.style.height = initialHeight;

			const showmore = document.createElement("div");
			showmore.className = "showmore";
			element.parentNode.insertBefore(showmore, element);

			const btnShowmore = document.createElement("div");
			btnShowmore.className = "btn_showmore";
			btnShowmore.textContent = "Read More ▼";
			element.parentNode.insertBefore(btnShowmore, element.nextSibling);

			const expandContent = () => {
				const fadeSpeed = 250;
				element.style.height = "auto";
				const fullHeight = element.offsetHeight;
				element.style.height = initialHeight;

				let duration = (fullHeight - parseInt(initialHeight)) / 10;
				duration = Math.min(duration, 150);
				duration += fadeSpeed;

				showmore.style.transition = `opacity ${fadeSpeed}ms`;
				showmore.style.opacity = "0";
				btnShowmore.style.transition = `opacity ${fadeSpeed}ms`;
				btnShowmore.style.opacity = "0";

				element.style.transition = `height ${duration}ms`;
				element.style.height = fullHeight + "px";

				setTimeout(() => {
					showmore.remove();
					btnShowmore.remove();
					element.style.height = "auto";
					element.style.transition = "";
					element.classList.remove("content_shortend");

					// Re-run formatMedia to ensure all images have proper handlers
					formatMedia();

					const thispage = element.parentNode
						.querySelector(".post_date")
						.getAttribute("href");
					const thispagetitle = element.parentNode.querySelector(
						".post_date_title .post_date"
					).textContent;
					_paq.push(["trackEvent", "postopen", thispage]);
					const url = window.location.origin + thispage;
					_paq.push(["setDocumentTitle", thispagetitle]);
					_paq.push(["setCustomUrl", url]);
					_paq.push(["trackPageView"]);
				}, duration);
			};

			showmore.addEventListener("click", expandContent);
			btnShowmore.addEventListener("click", expandContent);
		}
	}
}

function formatContent() {
	document.querySelectorAll(".content_main").forEach((element) => {
		formatContentHeight(element);
		element.querySelectorAll('a[href*="/tag/"]').forEach((link) => {
			if (link.textContent.startsWith("#")) {
				link.classList.add("hashtag-link");
			}
		});
	});

	if (window.location.pathname.startsWith("/p/") || window.location.pathname.includes("/p/")) {
		document.querySelectorAll('.e-content a[href*="/tag/"]').forEach((link) => {
			if (link.textContent.startsWith("#")) {
				link.classList.add("hashtag-link");
			}
		});
	}

	initTagSearch();
}

function initTagSearch() {
	const searchInput = document.getElementById("tagSearch");
	if (!searchInput) return; // Exit if we're not on the tags page

	const tagElements = document.querySelectorAll(".tag_container");

	function filterTags(searchTerm) {
		searchTerm = searchTerm.toLowerCase().trim();

		tagElements.forEach((tag) => {
			const tagName = tag.getAttribute("data-tag-name").toLowerCase();
			if (searchTerm === "") {
				tag.style.display = ""; // Show everything when search is empty
			} else {
				tag.style.display = tagName.includes(searchTerm) ? "" : "none";
			}
		});
	}

	// Add input event listener with debounce for better performance
	let debounceTimeout;
	searchInput.addEventListener("input", (e) => {
		clearTimeout(debounceTimeout);
		debounceTimeout = setTimeout(() => {
			filterTags(e.target.value);
		}, 150); // 150ms delay
	});
}

function formatMedia() {
	// Get all images that haven't been initialized
	const contentImages = document.querySelectorAll(
		".e-content img:not([data-gallery-initialized])"
	);

	contentImages.forEach((img) => {
		// Mark as initialized
		img.setAttribute("data-gallery-initialized", "true");

		// Add click listener
		img.addEventListener("click", (e) => {
			// If in edit mode, do not interfere
			if (editing) return;

			e.preventDefault();
			e.stopPropagation();

			// First handle expansion if needed
			const contentMain = img.closest(".content_main");
			if (
				contentMain?.classList.contains("content_shortend") &&
				contentMain.expandContent
			) {
				contentMain.expandContent(true); // true indicates it's from an image click
			}

			// Then show gallery
			const allImages = Array.from(
				document.querySelectorAll(".e-content img")
			).map((img) => img.src);
			const clickedIndex = Array.from(
				document.querySelectorAll(".e-content img")
			).indexOf(img);
			gallery.show(allImages, clickedIndex);
		});
	});
}

async function loadPageFromURL(url) {
	const timeItTookToLoadPage = Date.now();
	const loadingElement = document.getElementById("loading");

	try {
		const response = await fetch(url);
		const html = await response.text();

		if (html) {
			// Analytics
			_paq.push(["setDocumentTitle", url]);
			_paq.push(["setCustomUrl", url]);
			_paq.push(["setGenerationTimeMs", Date.now() - timeItTookToLoadPage]);
			_paq.push(["enableLinkTracking"]);
			_paq.push(["trackPageView"]);

			// Parse HTML and append content
			const parser = new DOMParser();
			const doc = parser.parseFromString(html, "text/html");
			const posts = doc.querySelectorAll(".h-entry");
			const postsContainer = document.getElementById("posts");

			// First append all posts
			posts.forEach((post) => {
				postsContainer.appendChild(post);
			});

			if (loadingElement) {
				loadingElement.style.display = "none";
			}

			// Update pagination
			const newPagination = doc.querySelector("#pagination_previous");
			if (newPagination) {
				const newPage = parseInt(newPagination.getAttribute("data-num"));
				if (!isNaN(newPage)) {
					currentPage = newPage;
				}
			} else {
				scrollend = true;
			}

			// Format content before media to set up the initial state
			formatDate();
			formatContent();

			// Initialize media last
			formatMedia();

			// Call additional formatting functions if they exist
			if (typeof repost === "function") repost();
			if (typeof editpost === "function") editpost();

			loading = false;
		} else {
			if (loadingElement) {
				loadingElement.style.display = "none";
			}
			scrollend = true;
			loading = false;
		}
	} catch (error) {
		console.error("Failed to load page:", error);
		if (loadingElement) {
			loadingElement.style.display = "none";
		}
		loading = false;
	}
}

function loadPage() {
	const paginationPrevious = document.getElementById("pagination_previous");
	const loadingElement = document.getElementById("loading");

	if (!paginationPrevious || currentPage < 0) {
		scrollend = true;
		return;
	}

	if (!scrollend && loadingElement) {
		loadingElement.style.display = "block";
	}

	if (!loading && !scrollend) {
		loading = true;

		// Build URL based on context
		let url;
		const urlParams = new URLSearchParams(window.location.search);

		if (window.location.href.includes("/tag/")) {
			const tag = window.location.pathname.split("/tag/")[1].replace("/", "");
			url = `/archive/tag/${tag}_${currentPage}.html`;
		} else if (window.location.href.includes("draft")) {
			url = `/archive/draft/${currentPage}.html`;
		} else if (window.location.pathname.startsWith("/search")) {
			// Handle search pages - preserve the search query
			const searchQuery = urlParams.get("q");
			url = `/archive/search/${currentPage}?q=${encodeURIComponent(
				searchQuery
			)}`;
		} else {
			url = `/archive/${currentPage}.html`;
		}

		loadPageFromURL(url);
	}
}

function infiniteScroll() {
	// Don't scroll on archive pages
	if (window.location.pathname.startsWith("/archive/")) {
		return;
	}

	// Get initial page number
	const paginationPrevious = document.getElementById("pagination_previous");
	if (paginationPrevious) {
		currentPage = parseInt(paginationPrevious.getAttribute("data-num"));
	}

	const paginationContainer = document.getElementById("pagination_container");
	if (paginationContainer) {
		paginationContainer.style.display = "none";

		// Load more results if initial page has few results
		if (document.querySelectorAll(".h-entry").length < 10) {
			loadPage();
		}
	}

	// Add scroll handler with debounce
	let scrollTimeout;
	window.addEventListener("scroll", () => {
		clearTimeout(scrollTimeout);
		scrollTimeout = setTimeout(() => {
			const scrollPosition = window.innerHeight + window.scrollY;
			const totalHeight = document.documentElement.scrollHeight;
			const threshold = 1000; // Trigger when within 1000px of bottom

			if (scrollPosition >= totalHeight - threshold) {
				loadPage();
			}
		}, 150);
	});
}

// Add necessary styles for the image gallery
const galleryStyles = document.createElement("style");
galleryStyles.textContent = `
    .gallery-nav {
        position: fixed;
        top: 50%;
        transform: translateY(-50%);
        background: rgba(255, 255, 255, 0.1);
        color: white;
        border: none;
        padding: 20px;
        cursor: pointer;
        font-size: 24px;
        z-index: 1003;
    }
    .gallery-nav.prev { left: 20px; }
    .gallery-nav.next { right: 20px; }
    .gallery-close {
        position: fixed;
        top: 20px;
        right: 20px;
        background: none;
        border: none;
        color: white;
        font-size: 40px;
        cursor: pointer;
        z-index: 1003;
    }
    .gallery-image-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        height: 100%;
    }
    /* Hide showmore overlay when image gallery is visible */
    .image-modal[style*="display: flex"] ~ .showmore {
        display: none !important;
    }
`;
document.head.appendChild(galleryStyles);

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
	// Initialize gallery first
	gallery = new ImageGallery();

	const loadingElement = document.getElementById("loading");
	if (loadingElement) {
		loadingElement.style.display = "none";
	}

	formatDate();

	if (!isMobile() && !isBot()) {
		infiniteScroll();
	}

	formatMedia();
	setTimeout(formatContent, 200);

	initTagSearch();
});

// Analytics setup
function loadAnalyticsScript() {
	const script = document.createElement("script");
	script.src = "/static/js/analytics.js"; // Adjust the path based on your project structure
	script.type = "text/javascript";
	script.async = true;
	document.head.appendChild(script);
}

// Call the function to load the analytics script
loadAnalyticsScript();
