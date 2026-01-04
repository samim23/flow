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
	// Comprehensive bot detection - includes search engines, AI crawlers, social previews, etc.
	const botPatterns = [
		// Major search engines
		'googlebot', 'bingbot', 'yandexbot', 'baiduspider', 'duckduckbot', 'slurp', 'sogou',
		// AI/LLM crawlers
		'gptbot', 'chatgpt', 'claude-web', 'anthropic', 'ccbot', 'perplexitybot', 'cohere-ai',
		// SEO tools
		'ahrefsbot', 'semrushbot', 'mj12bot', 'dotbot', 'rogerbot', 'screaming frog',
		// Social media previews
		'facebookexternalhit', 'twitterbot', 'linkedinbot', 'slackbot', 'telegrambot', 'whatsapp', 'discordbot',
		// Archive/research
		'ia_archiver', 'archive.org_bot', 'heritrix',
		// Generic patterns
		'bot', 'spider', 'crawl', 'wget', 'curl', 'python-urllib', 'python-requests', 'libwww',
		'httpunit', 'nutch', 'phpcrawl', 'httrack', 'java/', 'perl', 'ruby',
		// Other known bots
		'applebot', 'bytespider', 'petalbot', '360spider', 'seznambot', 'exabot',
		'gigablast', 'teoma', 'blexbot', 'linkdex', 'msnbot'
	];
	const pattern = new RegExp(botPatterns.join('|'), 'i');
	return pattern.test(navigator.userAgent);
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
	// Check if we're on a detail page (single post view)
	const isDetailPage = window.location.pathname.startsWith('/p/');
	
	if (!isBot()) {
		document.querySelectorAll(".post_date_title").forEach((el) => {
			el.style.display = "none";
		});
	}

	document
		.querySelectorAll(".dt-published:not([data-formatted])")
		.forEach((dateElem) => {
			const date = dateElem.getAttribute("datetime");
			if (!date) return;
			
			const dateObj = new Date(date);
			
			if (isDetailPage) {
				// On detail pages, show full date
				const fullDate = dateObj.toLocaleDateString('en-US', {
					weekday: 'long',
					year: 'numeric',
					month: 'long',
					day: 'numeric'
				});
				dateElem.textContent = fullDate;
			} else {
				// On list pages, show relative time
				const formatted = getRelativeTimeString(date);
				dateElem.textContent = formatted;
				
				// Add absolute date as title for hover tooltip
				const absoluteDate = dateObj.toLocaleString('en-US', {
					year: 'numeric',
					month: 'short',
					day: 'numeric',
					hour: '2-digit',
					minute: '2-digit'
				});
				dateElem.setAttribute("title", absoluteDate);
			}
			
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
					
					// Only use analytics if _paq is defined
					if (typeof _paq !== 'undefined') {
						_paq.push(["trackEvent", "postopen", thispage]);
						// Check if href is already absolute URL (static site) or relative (dev)
						const url = thispage.startsWith('http') ? thispage : window.location.origin + thispage;
						_paq.push(["setDocumentTitle", thispagetitle]);
						_paq.push(["setCustomUrl", url]);
						_paq.push(["trackPageView"]);
					}
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
			// Analytics - only if _paq is defined
			if (typeof _paq !== 'undefined') {
				_paq.push(["setDocumentTitle", url]);
				_paq.push(["setCustomUrl", url]);
				_paq.push(["setGenerationTimeMs", Date.now() - timeItTookToLoadPage]);
				_paq.push(["enableLinkTracking"]);
				_paq.push(["trackPageView"]);
			}

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
			
			// Initialize flow-embeds in newly loaded content
			initFlowEmbeds();

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

		// Get site path prefix to construct correct URLs
		const siteElement = document.getElementById('site');
		let pathPrefix = '';
		if (siteElement && siteElement.dataset.sitePathPrefix) {
			pathPrefix = siteElement.dataset.sitePathPrefix;
			// Remove trailing slash if present
			if (pathPrefix.endsWith('/')) {
				pathPrefix = pathPrefix.slice(0, -1);
			}
		}

		// Build URL based on context
		let url;
		const urlParams = new URLSearchParams(window.location.search);

		if (window.location.href.includes("/tag/")) {
			const tag = window.location.pathname.split("/tag/")[1].replace("/", "");
			url = `${pathPrefix}/archive/tag/${tag}_${currentPage}.html`;
		} else if (window.location.href.includes("draft")) {
			url = `${pathPrefix}/archive/draft/${currentPage}.html`;
		} else if (window.location.pathname.startsWith("/search") || window.location.pathname.includes("/search")) {
			// Handle search pages - preserve the search query
			const searchQuery = urlParams.get("q");
			url = `${pathPrefix}/archive/search/${currentPage}?q=${encodeURIComponent(
				searchQuery
			)}`;
		} else {
			url = `${pathPrefix}/archive/${currentPage}.html`;
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

	// Mobile gets larger threshold and longer debounce for stability
	const mobile = isMobile();
	const threshold = mobile ? 1500 : 1000; // Trigger earlier on mobile to feel smoother
	const debounceMs = mobile ? 250 : 150;  // Longer debounce on mobile to reduce load

	// Add scroll handler with debounce
	let scrollTimeout;
	window.addEventListener("scroll", () => {
		clearTimeout(scrollTimeout);
		scrollTimeout = setTimeout(() => {
			const scrollPosition = window.innerHeight + window.scrollY;
			const totalHeight = document.documentElement.scrollHeight;

			if (scrollPosition >= totalHeight - threshold) {
				loadPage();
			}
		}, debounceMs);
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

// Lazy load MathJax only when math content is detected
function lazyLoadMathJax() {
	// Check if page contains LaTeX math notation
	const content = document.body.innerHTML;
	const hasMath = /\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$[^$]+\$/s.test(content);
	
	if (hasMath && !window.MathJax) {
		console.log('Math content detected, loading MathJax...');
		
		// Configure MathJax before loading
		window.MathJax = {
			tex: {
				inlineMath: [['\\(', '\\)'], ['$', '$']],
				displayMath: [['\\[', '\\]'], ['$$', '$$']]
			},
			startup: {
				ready: () => {
					console.log('MathJax loaded and ready');
					MathJax.startup.defaultReady();
				}
			}
		};
		
		// Get site path prefix
		const siteElement = document.getElementById('site');
		let pathPrefix = '';
		if (siteElement && siteElement.dataset.sitePathPrefix) {
			pathPrefix = siteElement.dataset.sitePathPrefix.replace(/\/$/, '');
		}
		
		// Load MathJax script
		const script = document.createElement('script');
		script.src = `${pathPrefix}/static/js/vendor/mathjax/es5/tex-mml-chtml.js`;
		script.async = true;
		document.head.appendChild(script);
	}
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
	// Initialize gallery first
	gallery = new ImageGallery();

	// Smart sticky header: natural scroll at top, then hide/show on direction
	const header = document.getElementById("top-container");
	if (header) {
		let lastScrollY = 0;
		let headerHeight = header.offsetHeight;
		const scrollDelta = 10;
		let inNaturalZone = true;
		let returningToTop = false;
		
		window.addEventListener("scroll", () => {
			const currentScrollY = window.scrollY;
			
			// In the natural zone (near top of page)
			if (currentScrollY <= headerHeight) {
				
				// Coming back from smart sticky with header visible?
				if (!inNaturalZone && !header.classList.contains("header-hidden")) {
					returningToTop = true;
				}
				
				// If returning to top, wait until we're actually at the top
				if (returningToTop) {
					if (currentScrollY < 5) {
						// At the top - reset everything cleanly
						returningToTop = false;
						header.classList.remove("scrolled", "header-hidden", "header-animate");
						header.style.transform = "";
					}
					// Keep header as-is while returning
					inNaturalZone = true;
					lastScrollY = currentScrollY;
					return;
				}
				
				// Normal natural scroll - header moves with content
				header.classList.remove("scrolled", "header-hidden", "header-animate");
				header.style.transform = `translateY(-${currentScrollY}px)`;
				lastScrollY = currentScrollY;
				inNaturalZone = true;
				return;
			}
			
			// Just exited natural zone - ensure header is hidden, no animation yet
			if (inNaturalZone) {
				header.style.transform = "";
				header.classList.add("header-hidden");
				header.classList.add("scrolled");
				// Enable animations after a tick
				requestAnimationFrame(() => {
					header.classList.add("header-animate");
				});
				inNaturalZone = false;
				lastScrollY = currentScrollY;
				return;
			}
			
			// Past header height - smart sticky behavior with animations
			const scrollDiff = currentScrollY - lastScrollY;
			
			if (scrollDiff > scrollDelta) {
				// Scrolling down - hide header
				header.classList.add("header-hidden");
				lastScrollY = currentScrollY;
			} else if (scrollDiff < -scrollDelta) {
				// Scrolling up - show header
				header.classList.remove("header-hidden");
				lastScrollY = currentScrollY;
			}
		}, { passive: true });
	}

	const loadingElement = document.getElementById("loading");
	if (loadingElement) {
		loadingElement.style.display = "none";
	}

	formatDate();

	// Enable infinite scroll for all devices, but not for bots
	if (!isBot()) {
		infiniteScroll();
	}

	formatMedia();
	setTimeout(formatContent, 200);

	initTagSearch();
	
	// Lazy load MathJax if needed
	lazyLoadMathJax();
});

// Analytics setup
function loadAnalyticsScript() {
	// Get site path prefix
	const siteElement = document.getElementById('site');
	let pathPrefix = '';
	if (siteElement && siteElement.dataset.sitePathPrefix) {
		pathPrefix = siteElement.dataset.sitePathPrefix;
		// Remove trailing slash if present
		if (pathPrefix.endsWith('/')) {
			pathPrefix = pathPrefix.slice(0, -1);
		}
	}

	// Create global _paq array if not exists
	window._paq = window._paq || [];
	
	const script = document.createElement("script");
	script.src = `${pathPrefix}/static/js/analytics.js`; // Include the path prefix
	script.type = "text/javascript";
	script.async = true;
	document.head.appendChild(script);
}

// Call the function to load the analytics script
loadAnalyticsScript();

// ============================================
// Flow Embed - Render <flow-embed> as quote cards
// ============================================
function initFlowEmbeds() {
	const embeds = document.querySelectorAll('flow-embed:not([data-initialized])');
	
	embeds.forEach(embed => {
		embed.setAttribute('data-initialized', 'true');
		
		const url = embed.getAttribute('url');
		if (!url) {
			embed.innerHTML = '<span class="flow-embed-error">Missing URL</span>';
			return;
		}
		
		// Show loading state
		embed.innerHTML = '<div class="flow-embed-loading">Loading...</div>';
		
		// Fetch the page and extract content
		fetchAndRenderEmbed(embed, url);
	});
}

async function fetchAndRenderEmbed(embed, url) {
	try {
		// Extract the page path from URL for fetching
		// URL might be full (https://samim.io/p/slug/) or relative (/p/slug/)
		let fetchUrl = url;
		
		// If we're on localhost/dev, convert absolute URLs to relative for same-origin fetch
		const currentOrigin = window.location.origin;
		const urlObj = new URL(url, currentOrigin);
		
		// Extract just the path for fetching (works on any origin)
		if (urlObj.pathname.startsWith('/p/')) {
			fetchUrl = urlObj.pathname;
		}
		
		const response = await fetch(fetchUrl);
		
		if (!response.ok) {
			throw new Error(`Failed to fetch: ${response.status}`);
		}
		
		const html = await response.text();
		const parser = new DOMParser();
		const doc = parser.parseFromString(html, 'text/html');
		
		// Extract content from the page
		const entry = doc.querySelector('.h-entry');
		let title = doc.querySelector('title')?.textContent?.trim() || 
		              doc.querySelector('.post_date_title')?.textContent?.trim() ||
		              'Untitled';
		// Strip site name suffix from title (e.g., "Post Title - SiteName" -> "Post Title")
		// Get site name from meta tag, falling back to extracting from current page title
		const siteName = document.querySelector('meta[name="site-name"]')?.content || 
		                 document.title.split(' - ').pop();
		if (siteName) {
			const suffixPattern = new RegExp(`\\s*-\\s*${siteName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'i');
			title = title.replace(suffixPattern, '');
		}
		const dateElem = doc.querySelector('.dt-published');
		const date = dateElem?.getAttribute('datetime') || '';
		const formattedDate = date ? getRelativeTimeString(date) : '';
		
		// Get excerpt from content
		const contentElem = doc.querySelector('.e-content');
		let excerpt = '';
		if (contentElem) {
			// Strip HTML and get first ~140 chars
			const textContent = contentElem.textContent?.trim() || '';
			excerpt = textContent.substring(0, 140);
			if (textContent.length > 140) excerpt += '...';
		}
		
		// Get first image if available
		const firstImage = doc.querySelector('.e-content img');
		const imageUrl = firstImage?.src || '';
		
		// Get domain for display
		const domain = new URL(url, window.location.origin).hostname;
		
		// Build the card HTML
		const hasImage = imageUrl && !imageUrl.startsWith('data:');
		const cardClass = hasImage ? 'flow-embed-card' : 'flow-embed-card no-image';
		
		embed.innerHTML = `
			<a href="${url}" class="${cardClass}" target="_blank" rel="noopener">
				<div class="flow-embed-card-inner">
					${hasImage ? `
						<div class="flow-embed-image">
							<img src="${imageUrl}" alt="" loading="lazy">
						</div>
					` : ''}
					<div class="flow-embed-content">
						<div class="flow-embed-meta">
							<span class="flow-embed-domain">${domain}</span>
							${formattedDate ? `<span class="flow-embed-date">${formattedDate}</span>` : ''}
						</div>
						<div class="flow-embed-title">${escapeHtml(title)}</div>
						${excerpt ? `<div class="flow-embed-excerpt">${escapeHtml(excerpt)}</div>` : ''}
					</div>
				</div>
			</a>
		`;
		
	} catch (error) {
		console.error('Flow embed error:', error);
		// Show error state with fallback link
		embed.innerHTML = `<a href="${url}" class="flow-embed-error" target="_blank" rel="noopener">
			⚠️ Could not load preview: ${url}
		</a>`;
	}
}

function escapeHtml(text) {
	const div = document.createElement('div');
	div.textContent = text;
	return div.innerHTML;
}

// Run on page load and after dynamic content loads
document.addEventListener('DOMContentLoaded', initFlowEmbeds);

// Also expose globally so it can be called after content changes
window.initFlowEmbeds = initFlowEmbeds;

// ============================================
// Content Discovery - "More in [Tag]" + "Newest Stories"
// ============================================
function initContentDiscovery() {
	const discoveryContainer = document.getElementById('content-discovery');
	if (!discoveryContainer) return;
	
	const currentPath = discoveryContainer.dataset.currentPath;
	
	// Extract tags from JSON-LD on the page (search all JSON-LD scripts for one with keywords)
	const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
	let tags = [];
	for (const script of jsonLdScripts) {
		try {
			const jsonLd = JSON.parse(script.textContent);
			if (jsonLd.keywords) {
				tags = jsonLd.keywords.split(', ').filter(t => t.trim());
				break; // Found keywords, stop searching
			}
		} catch (e) {
			// Skip invalid JSON-LD scripts
		}
	}
	
	// Fetch RSS for top stories first
	const rssPromise = fetch('/rss.xml')
		.then(r => r.ok ? r.text() : null)
		.then(xml => xml ? parseRSS(xml, currentPath) : [])
		.catch(() => []);
	
	// Fetch tag pages with pagination support
	const tagsToFetch = tags.slice(0, 3);
	const tagPostsPromise = fetchTagPostsWithPagination(tagsToFetch, currentPath, 6);
	
	Promise.all([rssPromise, tagPostsPromise]).then(([topStories, tagPosts]) => {
		// Build mixed "More in Tags" section
		const mixedPosts = getMixedTagPosts(tagPosts, 6);
		
		// Render the discovery section
		renderDiscovery(discoveryContainer, tags, mixedPosts, topStories);
	});
}

// Fetch posts from tag pages, auto-paginating until we have enough
async function fetchTagPostsWithPagination(tags, excludePath, minPostsPerTag) {
	const tagPosts = new Map();
	
	for (const tag of tags) {
		const posts = [];
		const seenHrefs = new Set();
		let page = -1; // -1 means main tag page, 0+ means archive pages
		const maxPages = 3; // Don't fetch more than 3 pages per tag
		
		while (posts.length < minPostsPerTag && page < maxPages) {
			let url;
			if (page === -1) {
				url = `/tag/${encodeURIComponent(tag)}/`;
			} else {
				url = `/archive/tag/${encodeURIComponent(tag)}_${page}.html`;
			}
			
			try {
				const response = await fetch(url);
				if (!response.ok) break;
				
				const html = await response.text();
				const pagePosts = parseTagPage(html, excludePath);
				
				// Add unique posts
				let addedAny = false;
				for (const post of pagePosts) {
					if (!seenHrefs.has(post.href)) {
						seenHrefs.add(post.href);
						posts.push(post);
						addedAny = true;
					}
				}
				
				// If no new posts found, stop pagination
				if (!addedAny && page >= 0) break;
				
			} catch (e) {
				break;
			}
			
			page++;
		}
		
		if (posts.length > 0) {
			tagPosts.set(tag, posts);
		}
	}
	
	return tagPosts;
}

function parseTagPage(html, excludePath) {
	const parser = new DOMParser();
	const doc = parser.parseFromString(html, 'text/html');
	const posts = [];
	
	doc.querySelectorAll('.h-entry').forEach(entry => {
		const titleLink = entry.querySelector('.post_date_title a');
		const dateElem = entry.querySelector('.dt-published');
		const contentElem = entry.querySelector('.e-content');
		const firstImg = entry.querySelector('.e-content img');
		
		if (!titleLink) return;
		
		const href = titleLink.getAttribute('href');
		// Skip current post
		if (href && href.includes(excludePath)) return;
		
		const title = titleLink.textContent?.trim() || 'Untitled';
		const date = dateElem?.getAttribute('datetime') || '';
		const imageUrl = firstImg?.src || '';
		
		posts.push({ title, href, date, imageUrl });
	});
	
	return posts;
}

function parseRSS(xml, excludePath) {
	const parser = new DOMParser();
	const doc = parser.parseFromString(xml, 'text/xml');
	const posts = [];
	
	doc.querySelectorAll('item').forEach(item => {
		const title = item.querySelector('title')?.textContent || 'Untitled';
		const link = item.querySelector('link')?.textContent || '';
		const pubDate = item.querySelector('pubDate')?.textContent || '';
		
		// Skip current post
		if (link && link.includes(excludePath)) return;
		
		posts.push({ 
			title, 
			href: link, 
			date: pubDate ? new Date(pubDate).toISOString() : ''
		});
	});
	
	return posts.slice(0, 6); // Top 6 stories
}

// Fisher-Yates shuffle
function shuffleArray(array) {
	for (let i = array.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[array[i], array[j]] = [array[j], array[i]];
	}
	return array;
}

function getMixedTagPosts(tagPosts, maxPosts) {
	// Collect all posts from all tags
	const allPosts = [];
	const usedHrefs = new Set();
	
	for (const [tag, posts] of tagPosts.entries()) {
		for (const post of posts) {
			if (!usedHrefs.has(post.href)) {
				usedHrefs.add(post.href);
				allPosts.push({ ...post, tag });
			}
		}
	}
	
	// Shuffle for variety on each page load
	shuffleArray(allPosts);
	
	return allPosts.slice(0, maxPosts);
}

function renderDiscovery(container, tags, tagPosts, topStories) {
	// If nothing to show, hide container
	if (tagPosts.length === 0 && topStories.length === 0) {
		container.style.display = 'none';
		return;
	}
	
	let html = '<div class="discovery-wrapper">';
	
	// "More in Tags" section
	if (tagPosts.length > 0) {
		// Build title showing tags - use original tags from the page
		const allTags = tags.length > 0 ? tags : [...new Set(tagPosts.map(p => p.tag))];
		let tagDisplay;
		if (allTags.length === 1) {
			tagDisplay = `#${allTags[0]}`;
		} else if (allTags.length === 2) {
			tagDisplay = `#${allTags[0]} & #${allTags[1]}`;
		} else {
			// 3+ tags: show first 2, then "+ N more"
			const remaining = allTags.length - 2;
			tagDisplay = `#${allTags[0]}, #${allTags[1]} & ${remaining} more`;
		}
		
		html += `
			<div class="discovery-section discovery-tags">
				<h3 class="discovery-heading">More in ${tagDisplay}</h3>
				<div class="discovery-grid">
		`;
		
		tagPosts.forEach(post => {
			const hasImage = post.imageUrl && !post.imageUrl.startsWith('data:');
			html += `
				<a href="${post.href}" class="discovery-card ${hasImage ? '' : 'no-image'}">
					<div class="discovery-card-image">
						${hasImage ? `<img src="${post.imageUrl}" alt="" loading="lazy">` : '<div class="discovery-card-placeholder"></div>'}
					</div>
					<div class="discovery-card-title">${escapeHtml(post.title)}</div>
				</a>
			`;
		});
		
		html += `
				</div>
			</div>
		`;
	}
	
	// "Newest Stories" section
	if (topStories.length > 0) {
		html += `
			<div class="discovery-section discovery-top">
				<h3 class="discovery-heading">Newest Stories</h3>
				<ul class="discovery-list">
		`;
		
		topStories.forEach(story => {
			const timeAgo = story.date ? getRelativeTimeString(story.date) : '';
			html += `
				<li class="discovery-list-item">
					<a href="${story.href}">
						${timeAgo ? `<span class="discovery-date">${timeAgo}</span>` : ''}
						${escapeHtml(story.title)}
					</a>
				</li>
			`;
		});
		
		html += `
				</ul>
			</div>
		`;
	}
	
	html += '</div>';
	container.innerHTML = html;
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', initContentDiscovery);

// ============================================
// Sidebar: Welcome Message + Random Post + Popular
// ============================================

function initSidebar() {
	initWelcomeMessage();
	initRandomPost();
	
	// Check which mode we're in
	const popularDataEl = document.getElementById('popular-posts-data');
	const dynamicList = document.getElementById('popular-list-dynamic');
	
	if (popularDataEl) {
		// Static mode: JSON pool embedded, shuffle and render
		initPopularFromPool();
	} else if (dynamicList) {
		// Dev mode: fetch from API
		initPopularDev();
	}
}

// Static mode: Render shuffled selection from embedded JSON pool
function initPopularFromPool() {
	const dataEl = document.getElementById('popular-posts-data');
	const listEl = document.getElementById('popular-list');
	if (!dataEl || !listEl) return;
	
	try {
		const pool = JSON.parse(dataEl.textContent);
		if (!pool || pool.length === 0) {
			document.getElementById('sidebar-popular')?.remove();
			return;
		}
		
		// Shuffle the pool
		const shuffled = shuffleArray([...pool]);
		
		// Take first 12 (SIDEBAR_POPULAR_LIMIT)
		const selected = shuffled.slice(0, 12);
		
		// Render
		listEl.innerHTML = selected.map(post => {
			const title = escapeHtml(truncateText(post.title || post.path, 55));
			const tagsHtml = post.tags && post.tags.length > 0
				? `<span class="sidebar-tags">${post.tags.slice(0, 2).map(tag => 
					`<a href="/tag/${encodeURIComponent(tag)}/">#${escapeHtml(tag)}</a>`
				).join(' ')}</span>`
				: '';
			return `<li><a href="/p/${post.path}/">${title}</a>${tagsHtml}</li>`;
		}).join('');
		
		// Now apply mobile sidebar logic
		initMobileSidebar();
		
	} catch (e) {
		console.error('Failed to parse popular posts data:', e);
	}
}

// Fisher-Yates shuffle
function shuffleArray(array) {
	for (let i = array.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[array[i], array[j]] = [array[j], array[i]];
	}
	return array;
}

// Truncate text to max length
function truncateText(text, maxLength) {
	if (!text || text.length <= maxLength) return text;
	return text.substring(0, maxLength - 3) + '...';
}

// Mobile: Move sidebar after 5th post, limit visible popular posts
function initMobileSidebar() {
	// Only when sidebar is hidden (< 1420px)
	if (window.innerWidth >= 1420) return;
	
	const sidebar = document.getElementById('sidebar');
	const postsList = document.getElementById('posts');
	if (!sidebar || !postsList) return;
	
	// Get all post items (li.h-entry)
	const posts = postsList.querySelectorAll('li.h-entry');
	if (posts.length < 5) return;
	
	// Move sidebar after the 5th post
	posts[4].after(sidebar);
	sidebar.classList.add('sidebar-inline-mobile');
	
	// Limit visible popular posts to 5 on mobile
	const popularList = sidebar.querySelector('.sidebar-popular ul');
	if (!popularList) return;
	
	const popularItems = popularList.querySelectorAll('li');
	if (popularItems.length <= 5) return;
	
	// Hide posts 6+
	popularItems.forEach((item, i) => {
		if (i >= 5) item.classList.add('popular-hidden-mobile');
	});
	
	// Add "Show more" button
	const showMoreBtn = document.createElement('button');
	showMoreBtn.className = 'popular-show-more';
	showMoreBtn.textContent = 'Show more';
	showMoreBtn.onclick = () => {
		popularItems.forEach(item => item.classList.remove('popular-hidden-mobile'));
		showMoreBtn.remove();
	};
	popularList.after(showMoreBtn);
}

// Welcome message using localStorage
function initWelcomeMessage() {
	const welcomeEl = document.getElementById('sidebar-welcome');
	if (!welcomeEl) return;
	
	const STORAGE_KEY = 'samim_last_visit';
	const now = new Date();
	const lastVisitStr = localStorage.getItem(STORAGE_KEY);
	
	if (!lastVisitStr) {
		// First visit - store timestamp, don't show welcome
		localStorage.setItem(STORAGE_KEY, now.toISOString());
		return;
	}
	
	// Return visitor
	const lastVisit = new Date(lastVisitStr);
	
	// Count new posts since last visit
	countNewPostsSince(lastVisit).then(newCount => {
		const welcomeText = welcomeEl.querySelector('.welcome-text');
		const newPostsEl = welcomeEl.querySelector('.welcome-new-posts');
		
		if (welcomeText) {
			welcomeText.textContent = 'Welcome back!';
		}
		
		if (newPostsEl && newCount > 0) {
			const postWord = newCount === 1 ? 'post' : 'posts';
			const dateStr = formatLastVisitDate(lastVisit);
			if (newCount >= 50) {
				newPostsEl.textContent = `50+ new ${postWord} since ${dateStr}`;
			} else {
				newPostsEl.textContent = `${newCount} new ${postWord} since ${dateStr}`;
			}
		} else if (newPostsEl) {
			newPostsEl.style.display = 'none';
		}
		
		// Show the welcome section
		welcomeEl.style.display = 'block';
		
		// Update last visit timestamp
		localStorage.setItem(STORAGE_KEY, now.toISOString());
	});
}

function formatLastVisitDate(date) {
	const now = new Date();
	const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
	
	if (diffDays === 0) return 'earlier today';
	if (diffDays === 1) return 'yesterday';
	if (diffDays < 7) return `${diffDays} days ago`;
	if (diffDays < 30) {
		const weeks = Math.floor(diffDays / 7);
		return weeks === 1 ? 'last week' : `${weeks} weeks ago`;
	}
	
	// For longer periods, show the date
	return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

async function countNewPostsSince(lastVisit) {
	// Get site path prefix
	const siteElement = document.getElementById('site');
	let pathPrefix = '';
	if (siteElement && siteElement.dataset.sitePathPrefix) {
		pathPrefix = siteElement.dataset.sitePathPrefix.replace(/\/$/, '');
	}
	
	try {
		// Fetch posts.json which contains all post dates
		const response = await fetch(`${pathPrefix}/posts.json`);
		if (!response.ok) return 0;
		
		const posts = await response.json();
		const lastVisitTime = lastVisit.getTime();
		
		// Count posts published after last visit
		let count = 0;
		for (const post of posts) {
			if (post.date) {
				const postDate = new Date(post.date);
				if (postDate.getTime() > lastVisitTime) {
					count++;
					if (count >= 50) break; // Cap at 50
				}
			}
		}
		
		return count;
	} catch (e) {
		console.warn('Could not count new posts:', e);
		return 0;
	}
}

// Random post button
function initRandomPost() {
	const randomBtns = document.querySelectorAll('#random-post-nav, #random-post-btn');
	if (randomBtns.length === 0) return;
	
	randomBtns.forEach(btn => {
		btn.addEventListener('click', async (e) => {
			e.preventDefault();
			await navigateToRandomPost();
		});
	});
}

async function navigateToRandomPost() {
	// Get site path prefix
	const siteElement = document.getElementById('site');
	let pathPrefix = '';
	if (siteElement && siteElement.dataset.sitePathPrefix) {
		pathPrefix = siteElement.dataset.sitePathPrefix.replace(/\/$/, '');
	}
	
	try {
		const response = await fetch(`${pathPrefix}/posts.json`);
		if (!response.ok) {
			console.error('Could not load posts index');
			return;
		}
		
		const posts = await response.json();
		if (posts.length === 0) return;
		
		// Pick a random post
		const randomPost = posts[Math.floor(Math.random() * posts.length)];
		
		// Navigate to it
		window.location.href = randomPost.url;
	} catch (e) {
		console.error('Random post navigation failed:', e);
	}
}

// Dev mode: Load Popular posts via API
function initPopularDev() {
	const dynamicList = document.getElementById('popular-list-dynamic');
	if (!dynamicList) return;
	
	// Fetch from analytics API
	fetch('/analytics/api/popular')
		.then(r => r.ok ? r.json() : null)
		.then(data => {
			if (!data || !data.posts || data.posts.length === 0) {
				// No data - hide the section
				const popularSection = document.getElementById('sidebar-popular');
				if (popularSection) popularSection.style.display = 'none';
				return;
			}
			
			// Shuffle and take 12 for variety
			const shuffled = shuffleArray([...data.posts]);
			const selected = shuffled.slice(0, 12);
			
			// Render the posts with tags
			dynamicList.innerHTML = selected.map(post => {
				const title = escapeHtml(truncateText(post.title || post.path, 55));
				const tagsHtml = post.tags && post.tags.length > 0
					? `<span class="sidebar-tags">${post.tags.slice(0, 2).map(tag => 
						`<a href="/tag/${encodeURIComponent(tag)}/">#${escapeHtml(tag)}</a>`
					).join(' ')}</span>`
					: '';
				return `<li><a href="/p/${post.path}/">${title}</a>${tagsHtml}</li>`;
			}).join('');
			
			// Now that posts are loaded, apply mobile sidebar logic
			initMobileSidebar();
		})
		.catch(e => {
			console.warn('Could not load popular posts:', e);
			const popularSection = document.getElementById('sidebar-popular');
			if (popularSection) popularSection.style.display = 'none';
		});
}

// Initialize sidebar on DOM ready
document.addEventListener('DOMContentLoaded', initSidebar);

// ============================================
// Got a Tip? Form
// ============================================
function initTipForm() {
	const textarea = document.getElementById('tip-textarea');
	const submitBtn = document.getElementById('tip-submit');
	const tipForm = document.getElementById('tip-form');
	const tipThanks = document.getElementById('tip-thanks');
	
	if (!textarea || !submitBtn) return;
	
	// Show/hide submit button based on text content
	textarea.addEventListener('input', () => {
		const hasText = textarea.value.trim().length > 0;
		submitBtn.style.display = hasText ? 'block' : 'none';
	});
	
	// Handle form submission
	submitBtn.addEventListener('click', () => {
		const tipText = textarea.value.trim();
		if (!tipText) return;
		
		// Create mailto link with pre-filled content (email obfuscated to deter scrapers)
		const subject = encodeURIComponent('Tip for samim.io');
		const body = encodeURIComponent(tipText);
		const e = ['tip', 'samim', 'io'].join('@').replace('@io', '.io');
		const mailtoUrl = `mailto:${e}?subject=${subject}&body=${body}`;
		
		// Open email client
		window.location.href = mailtoUrl;
		
		// Show thank you message
		tipForm.style.display = 'none';
		tipThanks.style.display = 'flex';
		
		// Optional: Reset after some time so user can send another tip
		setTimeout(() => {
			textarea.value = '';
			submitBtn.style.display = 'none';
			tipForm.style.display = 'flex';
			tipThanks.style.display = 'none';
		}, 5000);
	});
}

// Initialize tip form on DOM ready
document.addEventListener('DOMContentLoaded', initTipForm);
