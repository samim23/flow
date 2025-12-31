// /app/static/js/main.js

var editing = false;
var editor2 = "";
var post_container = "";
var post_date = "";
var post_tags = "";
var post_edit = "";
var post_edit_id = "";
var content_temp = "";
var filename_maxlength = 55;
var uploadsInProgress = 0;
var cachedTags = null; // Cache for tag autocomplete
var autosaveInterval = null;
var AUTOSAVE_KEY = 'flow_draft_autosave';
var AUTOSAVE_TIMESTAMP_KEY = 'flow_draft_timestamp';

// Check if content contains blob URLs (indicates upload in progress)
function contentHasBlobUrls(content) {
	return /blob:/.test(content);
}

String.prototype.replaceAll = function (searchStr, replaceStr) {
	var str = this;
	searchStr = searchStr.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
	return str.replace(new RegExp(searchStr, "gi"), replaceStr);
};

function strip(html) {
	var doc = new DOMParser().parseFromString(html, "text/html");
	return doc.body.textContent || "";
}

function strip2(html) {
	var doc = new DOMParser().parseFromString(html, "text/html");
	doc = doc.body.innerHTML.replace(/<(?:.|\n)*?>/gm, " ");
	return doc || "";
}

function truncate(string, len) {
	if (string.length > len) return string.substring(0, len) + "...";
	else return string;
}

function linkify(elContent) {
	const siteElement = document.getElementById('site');
	let sitePathPrefix = '';
	if (siteElement && siteElement.dataset.sitePathPrefix) {
		sitePathPrefix = siteElement.dataset.sitePathPrefix.replace(/\/$/, ''); // Remove trailing slash
		
		// Sanitize Windows paths
		// 1. Remove drive letters and paths
		sitePathPrefix = sitePathPrefix.replace(/^[A-Za-z]:([/\\].*)$/, '$1');
		// 2. Remove Git paths
		sitePathPrefix = sitePathPrefix.replace(/^[/\\]Git([/\\]|$)/, '/');
		
		// Ensure prefix starts with / if not empty
		if (sitePathPrefix && !sitePathPrefix.startsWith('/')) {
			sitePathPrefix = '/' + sitePathPrefix;
		}
	}

	return (elContent = linkifyHtml(elContent, {
		nl2br: false, // optional
		formatHref: {
			hashtag: (href) => `${sitePathPrefix}/tag/${href.replace("#", "")}`,
			mention: (val) => "https://twitter.com/" + val.substr(1),
		},
		validate: {
			url: (val) => /^https?:\/\//.test(val), // only allow URLs that begin with a protocol
			email: false, // don't linkify emails
		},
		className: { hashtag: "hashtag" },
	}));
}

function slugify(text) {
	return text
		.toString()
		.toLowerCase()
		.replace(/\s+/g, "-") // Replace spaces with -
		.replace(/[^\w\-]+/g, "") // Remove all non-word chars
		.replace(/\-\-+/g, "-") // Replace multiple - with single -
		.replace(/^-+/, "") // Trim - from start of text
		.replace(/-+$/, "") // Trim - from end of text
		.replace(/[\s_-]+/g, "-");
}

// Generate readable alt text from filename for SEO
function generateAltFromFilename(filename) {
	if (!filename) return 'Image';
	
	// Remove file extension
	var name = filename.replace(/\.[^/.]+$/, '');
	
	// Remove common prefixes (dates, random hashes)
	name = name
		.replace(/^\d{4}-\d{2}-\d{2}-?/, '')  // Remove date prefixes like 2024-01-15-
		.replace(/^[a-f0-9]{8,}-?/i, '')       // Remove hash prefixes
		.replace(/-[a-f0-9]{8,}$/i, '');       // Remove hash suffixes
	
	// Replace dashes, underscores, and camelCase with spaces
	name = name
		.replace(/[-_]+/g, ' ')                // Replace dashes/underscores with spaces
		.replace(/([a-z])([A-Z])/g, '$1 $2')   // Split camelCase
		.replace(/\s+/g, ' ')                  // Collapse multiple spaces
		.trim();
	
	// Capitalize first letter of each word (title case)
	name = name.toLowerCase().replace(/\b\w/g, function(l) { return l.toUpperCase(); });
	
	// If name is empty or too short after cleaning, use a generic fallback
	if (!name || name.length < 2) {
		return 'Image';
	}
	
	// Truncate if too long (max 100 chars for alt text)
	if (name.length > 100) {
		name = name.substring(0, 100).trim();
	}
	
	return name;
}

function cleanContent(elContent) {
	function replaceLast(str, word, newWord) {
		str = str.trim();
		if (!str.endsWith(word)) {
			return str;
		}
		var n = str.lastIndexOf(word);
		return str.slice(0, n) + str.slice(n).replace(word, newWord);
	}

	elContent = elContent.replaceAll(' scrolling="no"', ""); // medium insert bug fix
	elContent = elContent.replaceAll(' class=""', ""); // medium insert bug fix
	elContent = elContent.replaceAll(" medium-insert-active", ""); // medium insert bug fix
	elContent = elContent.replaceAll(' contenteditable="false"', ""); // medium insert bug fix
	elContent = elContent.replaceAll("<b></b>", ""); // medium insert bug fix
	elContent = elContent.replaceAll("<p><br></p>", ""); // medium insert bug fix
	elContent = replaceLast(elContent, "<p><br></p>", ""); // medium insert bug fix

	// Clean up any remaining blob URLs - replace with their proper uploaded path
	// Blob URLs will have already been replaced with proper paths if upload completed
	// This is a fallback to prevent blob URLs being saved
	elContent = elContent.replace(/src="blob:[^"]+"/g, 'src="" alt="Image upload in progress"');

	var tempDom = $("<o>").append($.parseHTML(elContent));
	// tempDom.find('*').removeAttr('style');
	tempDom.find("a").removeAttr("style");
	tempDom.find("p").removeAttr("style");
	tempDom.find("span").removeAttr("style");
	tempDom.find("blockquote").removeAttr("style");
	tempDom.find("a").removeAttr("class");
	tempDom.find("img").removeAttr("data-gallery-initialized");
	tempDom.find(".medium-insert-buttons").remove();
	
	// Clean flow-embed elements: keep only the URL attribute, remove rendered content
	tempDom.find("flow-embed").each(function() {
		var url = $(this).attr("url");
		$(this).empty(); // Remove all inner content
		$(this).removeAttr("data-initialized"); // Remove runtime attribute
		$(this).removeAttr("data-cursor-ref"); // Remove cursor ref
		$(this).attr("url", url); // Ensure URL is preserved
	});
	
	// Remove any orphaned flow-embed card elements that ended up outside the tag
	tempDom.find(".flow-embed-card, .flow-embed-card-inner, .flow-embed-loading, .flow-embed-error").remove();
	tempDom.find(".flow-embed-image, .flow-embed-content, .flow-embed-meta, .flow-embed-domain, .flow-embed-title, .flow-embed-excerpt, .flow-embed-date").remove();
	
	// Remove orphaned empty anchor tags (leftover from flow-embed rendering)
	tempDom.find("a").each(function() {
		var linkText = $(this).text().trim();
		var href = $(this).attr("href") || "";
		// Remove if it's empty (just whitespace) or only contains flow-embed classes
		if (linkText === "" || (href.includes("/p/") && linkText === "")) {
			$(this).remove();
		}
	});
	
	// Remove data-cursor-ref attributes
	tempDom.find("[data-cursor-ref]").removeAttr("data-cursor-ref");
	
	// Clean up empty paragraphs
	tempDom.find("p").each(function() {
		if ($(this).html().trim() === "" || $(this).html().trim() === "<br>") {
			$(this).remove();
		}
	});
	
	return tempDom.html().trim();
}

function getHashtag(text) {
	var text = strip2(text);
	var found_hashes = [];
	var format = /[ !@$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/;
	function hasWhiteSpace(s) {
		return /\s/g.test(s);
	}
	var matched = text.match(/(\S*#\[[^\]]+\])|(\S*#\S+)/gi);

	if (text.length <= 0 || matched == null) {
		var hashstring = "[]";
		return [hashstring, found_hashes];
	}
	[].forEach.call(matched, function (m) {
		tag = m.split("#")[1];
		tag_final = "";
		for (var i = 0; i < tag.length; i++) {
			// stop on any space or special chars
			if (format.test(tag[i]) || hasWhiteSpace(tag[i])) {
				break;
			}
			tag_final += tag[i];
		}
		tag_final = tag_final.replace(/[^a-z0-9]/gi, "");
		if (tag_final.length >= 1) {
			found_hashes.push(tag_final);
		}
	});

	// find unique hashtags
	var final_hash = [];
	for (hash in found_hashes) {
		if (
			$.inArray(found_hashes[hash], final_hash) == -1 &&
			found_hashes[hash] != ""
		) {
			final_hash.push(found_hashes[hash]);
		}
	}
	// found hastags to string
	var hashstring = "[" + final_hash.toString() + "]";
	return [hashstring, final_hash];
}

// setup editor
function editor_setup(container, editor) {
	container.mediumInsert({
		editor: editor,
		addons: {
			images: {
				preview: true,
				captions: true,
				captionPlaceholder: "Type caption for image (optional)",
				autoGrid: 3,
				fileUploadOptions: {
					url: "/upload",
					paramName: "file",
					acceptFileTypes: /(\.|\/)(gif|jpe?g|png|webp)$/i,
					singleFileUploads: true,
					sequentialUploads: true,
					add: function (e, data) {
						// Show UI before anything else happens
						uploadsInProgress++;
						// console.log(`File queued (${uploadsInProgress} total)`);

						// Show the global upload indicator first
						$(".note_publish")
							.html(
								`<b>Uploading</b><br/><img src="/static/img/loading.gif" title="Uploading..." width="39"/>`
							)
							.show(); // Changed to show() instead of slideDown for immediacy
						$("#submit_btn").hide();

						// Then add the image overlay
						var $imageContainer = $(e.target).closest("figure");
						if (!$imageContainer.find(".upload-overlay").length) {
							$imageContainer.append(
								'<div class="upload-overlay" style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.8); display: flex; justify-content: center; align-items: center; z-index: 1000;"><div class="upload-progress" style="text-align: center; color: #333;"><b>Preparing...</b><br/><img src="/static/img/loading.gif" width="39"/></div></div>'
							);
						}
						
						// Store the blob URL for later replacement
						if (data.files && data.files[0]) {
							var blobUrl = URL.createObjectURL(data.files[0]);
							data.blobUrl = blobUrl;
							$imageContainer.attr('data-blob-url', blobUrl);
						}
						
						return data.submit();
					},
					xhr: function () {
						var xhr = $.ajaxSettings.xhr();
						if (xhr.upload) {
							xhr.upload.addEventListener(
								"progress",
								function (e) {
									if (e.lengthComputable) {
										var percentComplete = Math.round(
											(e.loaded / e.total) * 100
										);
										// Update both indicators
										$(".note_publish")
											.html(
												`<b>Uploading<br/><img src="/static/img/loading.gif" title="Uploading..." width="39"/>`
											)
											.show();
									}
								},
								false
							);
						}
						return xhr;
					},
					start: function (e, data) {
						// console.log(`Upload started (${uploadsInProgress} total)`);
					},
					stop: function (e, data) {
						// console.log(`All uploads complete (${uploadsInProgress} total)`);
						uploadsInProgress = 0; // Reset counter

						var completeHtml =
							'<b>Upload complete!</b><br/><img src="/static/img/loading.gif" title="Complete" width="39"/>';
						$(".note_publish").html(completeHtml).show();
						$(".upload-overlay .upload-progress").html(completeHtml);

						setTimeout(() => {
							$(".note_publish").slideUp("slow", function () {
								$("#submit_btn").show();
							});
							$(".upload-overlay").fadeOut("slow", function () {
								$(this).remove();
							});
						}, 800);
					},
					fail: function (e, data) {
						uploadsInProgress--;
						// console.log(`Upload failed (${uploadsInProgress} remaining)`);

						if (uploadsInProgress <= 0) {
							var failHtml = "<b>Upload failed</b><br/>Please try again";
							$(".note_publish").html(failHtml);
							$(".upload-overlay .upload-progress").html(failHtml);

							setTimeout(() => {
								$(".note_publish").slideUp("slow", function () {
									$("#submit_btn").show();
								});
								$(".upload-overlay").fadeOut("slow", function () {
									$(this).remove();
								});
							}, 2000);

							uploadsInProgress = 0;
						}
					},
					done: function(e, data) {
						// Replace the blob URL with the actual file URL in the HTML
						if (data.blobUrl && data.result && data.result.files && data.result.files[0]) {
							var actualUrl = data.result.files[0].url;
							var originalFilename = data.result.files[0].name || '';
							
							// Generate alt text from filename
							var altText = generateAltFromFilename(originalFilename);
							
							// Find images with this blob URL and update them
							$('img[src="' + data.blobUrl + '"]').attr('src', actualUrl).attr('alt', altText);
							
							// Also find by the data attribute (more reliable)
							var $figure = $('figure[data-blob-url="' + data.blobUrl + '"]');
							$figure.find('img').attr('src', actualUrl).attr('alt', altText);
							$figure.removeAttr('data-blob-url');
							
							// Revoke the blob URL to free memory
							URL.revokeObjectURL(data.blobUrl);
						}
					}
				},
			},
			embeds: {
				// (object) Embeds addon configuration
				label: '<span class="fa fa-youtube-play"></span>', // (string) A label for an embeds addon
				placeholder:
					"Paste a YouTube, Vimeo, Facebook, Twitter or Instagram link and press Enter", // (string) Placeholder displayed when entering URL to embed
				captions: true, // (boolean) Enable captions
				captionPlaceholder: "Type caption (optional)", // (string) Caption placeholder
				oembedProxy: "http://medium.iframe.ly/api/oembed?iframe=1", // (string/null).
				styles: {
					// (object) Available embeds styles configuration
					wide: {
						// (object) Embed style configuration. Key is used as a class name added to an embed, when the style is selected (.medium-insert-embeds-wide)
						label: '<span class="fa fa-align-justify"></span>', // (string) A label for a style
						added: function ($el) {}, // (function) Callback function called after the style was selected. A parameter $el is a current active paragraph (.medium-insert-active)
						removed: function ($el) {}, // (function) Callback function called after a different style was selected and this one was removed.
					},
					left: {
						label: '<span class="fa fa-align-left"></span>',
					},
					right: {
						label: '<span class="fa fa-align-right"></span>',
					},
				},
				actions: {
					// (object) Actions for an optional second toolbar
					remove: {
						// (object) Remove action configuration
						label: '<span class="fa fa-times"></span>', // (string) Label for an action
						clicked: function ($el) {
							// (function) Callback function called when an action is selected
							var $event = $.Event("keydown");
							$event.which = 8;
							$(document).trigger($event);
						},
					},
				},
			},
		},
	});
	return editor;
}

// create editor
function editor_create(container, submit_btn) {
	var editor = new MediumEditor(container, {
		toolbar: {
			buttons: [
				"bold",
				"italic",
				"underline",
				"anchor",
				"h2",
				"h3",
				"quote",
				"unorderedlist",
				"orderedlist",
			],
		},
		placeholder: false,
		paste: {
			forcePlainText: true,
			cleanPastedHTML: false,
			cleanReplacements: [],
			cleanTags: [],
			cleanAttrs: [],
			unwrapTags: [],
		},
	});

	// check for changes in the editor
	editor.subscribe("editableInput", function (event, editable) {
		var elContent =
			editor.serialize()[Object.keys(editor.serialize())[0]].value;

		if (strip(elContent).length > 0) {
			submit_btn.show();
			$("#related_btn").show(); // Show related button when content exists
			$(".note_publish").slideUp("fast"); // Ensure indicator is hidden
			$("#editor_placeholder").hide(); // Hide placeholder when content exists
		} else {
			submit_btn.hide();
			$("#related_btn").hide(); // Hide related button when empty
			$("#editor_placeholder").show(); // Show placeholder when empty
		}
	});

	// Setup tag autocomplete for this editor
	setupTagAutocompleteForEditor(container);
	
	return editor_setup(container, editor);
}

function makePostString(
	post_date,
	hashtags,
	status,
	author,
	author_name,
	link,
	icon,
	elContent
) {
	// Check if post is image-only (for better fallback title)
	const hasImage = /<img|<figure/.test(elContent);
	const textContent = elContent.replace(/<[^>]*>?/gm, "").trim();
	
	// Ensure title sanitization
	let title = elContent.trim();
	title = title.replace(/<[^>]*>?/gm, ""); // strip HTML
	title = title.replace(/(?:https?|ftp):\/\/[\n\S]+/g, ""); // strip links
	title = title.replace(/#\w+/g, ""); // remove entire hashtags (not just # symbol)
	title = title.replace(/\n\s*\n/g, "\n"); // replace multi line breaks with single
	title = title.replace(/\n/g, ". "); // replace line breaks with dot
	title = title.replace(/\r\n|\n|\r/gm, ""); // remove line breaks
	title = title.replace(/\s+/g, " "); // remove extra spaces
	title = title.replace(/:/g, " -"); // replace colons
	title = title.replace(/['"""]/g, ""); // remove quotes
	title = title.replace(/\.+/g, "."); // collapse multiple dots
	title = title.replace(/^\.\s*/, ""); // remove leading dots
	title = title.trim();
	
	// Smart fallback for empty titles
	if (!title) {
		if (hasImage) {
			title = "Image";
		} else {
			title = "Untitled";
		}
	}

	title = truncate(title, 70); // Truncate title

	// Ensure post_date is valid
	post_date = post_date || new Date().toISOString(); // Fallback to current date

	// Generate YAML frontmatter
	const frontmatter = `---
title: "${title}"
date: ${post_date}
tags: ${hashtags}
status: ${status || "draft"}
author: ${author || ""}
author_name: "${author_name || ""}"
link: "${link || ""}"
icon: "${icon || ""}"
---
`;

	// Combine frontmatter with content
	const markdown = frontmatter + "\n" + elContent;

	return [markdown, title];
}

editpost = function () {
	$(".post_dropdown").unbind("click");
	$(".post_delete").unbind("click");
	$(".post_edit").unbind("click");

	// edit post dropdown
	$(".post_dropdown").click(function (event) {
		post_container = $(event.target).closest(".h-entry");
		post_tags = post_container.find(".post_tags");
		post_date = post_container.find(".dt-published").attr("datetime");
		post_edit = post_container.find(".e-content");
		post_edit_id = $(event.target).attr("href");
	});
	// delete post
	$(".post_delete").click(function (event) {
		event.preventDefault();
		$.ajax({
			url: "/delete",
			data: { path: post_edit_id },
			type: "POST",
			success: function (response) {
				$(post_container).slideUp("fast", function () {
					$(this).remove();
				});
			},
			error: function (error) {
				console.log(error);
			},
		});
	});

	// edit post
	$(".post_edit").click(function (event) {
		// reset editor + destory old editor
		event.preventDefault();
		post_edit.addClass(".editable");
		if (editor2 != "") {
			editor2.destroy();
		}
		$(".content_btn").remove();
		// expand "showmore" hidden content
		var showmore = post_container.find(".showmore").trigger("click");
		editing = true;
		var btn_container = $("<span/>", { class: "content_btn" });
		$(post_edit).before(btn_container);
		// add new editor
		editor2 = editor_create(post_edit, btn_container);
		post_edit.mediumInsert("enable");
		// save current content to restore on cancel
		var allContents = editor2.serialize();
		var elContent = allContents["element-0"].value;
		content_temp = elContent;
		// focus text field
		post_edit.focus();
		// button status
		// var btn_status = $("<select/>", { class: "content_btn btn_select" });
		// var btn_status_options = ["public", "private"];
		// for (var i in btn_status_options) {
		// 	btn_status.append($("<option/>").html(btn_status_options[i]));
		// }
		// var currentStatus = post_container.find(".post_status");
		// if (currentStatus.length == 0) {
		// 	currentStatus = btn_status_options[0];
		// } else {
		// 	currentStatus = btn_status_options[1];
		// }
		// btn_status.val(currentStatus);
		// btn_container.append(btn_status);

		// button cancel
		var btn_cancel = $("<button/>", {
			class: "content_btn btn_cancel",
			text: "Cancel",
			click: function () {
				// restore content and destroy editor
				editor2.setContent(content_temp);
				editor2.destroy();
				$(".content_btn").remove();
				post_edit.removeClass(".editable");
				editing = false;
			},
		});
		btn_container.append(btn_cancel);

		// button save
		var btn_save = $("<button/>", {
			class: "content_btn btn_save",
			text: "Save",
			click: function () {
				// get editor content
				var allContents = editor2.serialize();
				var elContent = allContents["element-0"].value;

				// Check for blob URLs - if found, alert user to wait for uploads
				if (contentHasBlobUrls(elContent)) {
					alert("Please wait for image uploads to complete before saving.");
					return;
				}

				editing = false;
				post_edit.removeClass(".editable");
				$(".content_btn").remove();

				elContent = cleanContent(elContent);
				var hashtags = getHashtag(elContent)[0];
				elContent = linkify(elContent);
				elContent = elContent.replaceAll(' class="hashtag"', ""); // linkify default class bug fix

				editor2.setContent(elContent);
				editor2.destroy();

				// prepare data to submit
				// var status = btn_status.val();
				var status = "public";
				var author = $("#site").attr("author");
				var icon = $("#site").attr("author_image");
				var author_name = $("#site").attr("author_name");
				var link = "/";

				var poststring = makePostString(
					post_date,
					hashtags,
					status,
					author,
					author_name,
					link,
					icon,
					elContent
				);
				var text = poststring[0];
				var title = poststring[1];

				// submit content
				$.ajax({
					url: "/post",
					data: { text: text, path: post_edit_id, unique: false },
					type: "POST",
					success: function (response) {
						post_container
							.find(".p-author")
							.attr("href", "/feed/" + author + "/");
						post_container.find(".p-author b").html(author_name);
						post_container
							.find(".post_user_icon")
							.css("background-image", "url(" + icon + ")");
						// console.log("post saved", response);
					},
					error: function (error) {
						console.log(error);
					},
				});
			},
		});
		btn_container.append(btn_save);
	});
};

function makeid(amount) {
	var text = "";
	var possible = "abcdefghijklmnopqrstuvwxyz0123456789";
	for (var i = 0; i < amount; i++)
		text += possible.charAt(Math.floor(Math.random() * possible.length));
	return text;
}

// Helper function to format the current date and time
function getFormattedDate() {
	var now = new Date();
	return (
		now.getFullYear() +
		"-" +
		String(now.getMonth() + 1).padStart(2, "0") +
		"-" +
		String(now.getDate()).padStart(2, "0") +
		" " +
		String(now.getHours()).padStart(2, "0") +
		":" +
		String(now.getMinutes()).padStart(2, "0") +
		":" +
		String(now.getSeconds()).padStart(2, "0")
	);
}

// Another helper function to format date for filenames
function getDateForFilename() {
	var now = new Date();
	return (
		now.getFullYear() +
		"-" +
		String(now.getMonth() + 1).padStart(2, "0") +
		"-" +
		String(now.getDate()).padStart(2, "0") +
		"-"
	);
}

function contentHasBlobUrls(content) {
	return /src="blob:[^"]+"/g.test(content);
}

// Draft Autosave Functions
function saveDraft(editor) {
	if (uploadsInProgress > 0) {
		console.log('Skipping autosave - uploads in progress');
		return false;
	}
	
	try {
		var elContent = editor.serialize()[Object.keys(editor.serialize())[0]].value;
		
		// Don't save empty content
		if (strip(elContent).length === 0) {
			return false;
		}
		
		// Don't save if content has blob URLs (upload in progress)
		if (contentHasBlobUrls(elContent)) {
			console.log('Skipping autosave - blob URLs detected');
			return false;
		}
		
		localStorage.setItem(AUTOSAVE_KEY, elContent);
		localStorage.setItem(AUTOSAVE_TIMESTAMP_KEY, Date.now().toString());
		console.log('Draft autosaved at', new Date().toLocaleTimeString());
		return true;
	} catch (e) {
		console.error('Autosave failed:', e);
		return false;
	}
}

function getDraft() {
	try {
		var content = localStorage.getItem(AUTOSAVE_KEY);
		var timestamp = localStorage.getItem(AUTOSAVE_TIMESTAMP_KEY);
		
		if (content && timestamp) {
			return {
				content: content,
				timestamp: parseInt(timestamp),
				timeAgo: getRelativeTimeString(parseInt(timestamp))
			};
		}
	} catch (e) {
		console.error('Failed to get draft:', e);
	}
	return null;
}

function getRelativeTimeString(timestamp) {
	var now = Date.now();
	var diff = now - timestamp;
	var seconds = Math.floor(diff / 1000);
	var minutes = Math.floor(seconds / 60);
	var hours = Math.floor(minutes / 60);
	var days = Math.floor(hours / 24);
	
	if (seconds < 60) return 'just now';
	if (minutes === 1) return 'a minute ago';
	if (minutes < 60) return minutes + ' minutes ago';
	if (hours === 1) return 'an hour ago';
	if (hours < 24) return hours + ' hours ago';
	if (days === 1) return 'yesterday';
	return days + ' days ago';
}

function clearDraft() {
	try {
		localStorage.removeItem(AUTOSAVE_KEY);
		localStorage.removeItem(AUTOSAVE_TIMESTAMP_KEY);
		console.log('Draft cleared');
	} catch (e) {
		console.error('Failed to clear draft:', e);
	}
}

function startAutosave(editor) {
	// Clear any existing interval
	if (autosaveInterval) {
		clearInterval(autosaveInterval);
	}
	
	// Autosave every 30 seconds
	autosaveInterval = setInterval(function() {
		saveDraft(editor);
	}, 30000);
	
	// Also save on blur (when user leaves the editor)
	$('.editable').on('blur', function() {
		saveDraft(editor);
	});
}

function stopAutosave() {
	if (autosaveInterval) {
		clearInterval(autosaveInterval);
		autosaveInterval = null;
	}
}

function showDraftRestorePrompt(draft, editor) {
	var restoreDiv = $('<div/>', {
		id: 'draft-restore-prompt',
		css: {
			background: '#fffce8',
			border: '1px solid #f0e68c',
			borderRadius: '8px',
			padding: '12px 16px',
			marginBottom: '12px',
			display: 'flex',
			justifyContent: 'space-between',
			alignItems: 'center',
			flexWrap: 'wrap',
			gap: '10px'
		}
	});
	
	var textSpan = $('<span/>').html(
		'<strong>📝 Draft found</strong> from ' + draft.timeAgo + 
		'. <span style="color:#666;">(' + new Date(draft.timestamp).toLocaleString() + ')</span>'
	);
	
	var buttonContainer = $('<div/>', { css: { display: 'flex', gap: '8px' } });
	
	var restoreBtn = $('<button/>', {
		text: 'Restore',
		css: {
			background: '#2fbc5c',
			color: 'white',
			border: 'none',
			padding: '6px 14px',
			borderRadius: '4px',
			cursor: 'pointer',
			fontWeight: '600'
		},
		click: function() {
			editor.setContent(draft.content);
			$('#draft-restore-prompt').slideUp(function() { $(this).remove(); });
			$('#submit_btn').show();
		}
	});
	
	var discardBtn = $('<button/>', {
		text: 'Discard',
		css: {
			background: '#fff',
			color: '#666',
			border: '1px solid #ddd',
			padding: '6px 14px',
			borderRadius: '4px',
			cursor: 'pointer'
		},
		click: function() {
			clearDraft();
			$('#draft-restore-prompt').slideUp(function() { $(this).remove(); });
		}
	});
	
	buttonContainer.append(restoreBtn, discardBtn);
	restoreDiv.append(textSpan, buttonContainer);
	
	$('#edit_container').prepend(restoreDiv);
}

function newpost() {
	var editor = editor_create($(".editable"), $("#submit_btn"));
	
	// Check for saved draft
	var draft = getDraft();
	if (draft) {
		showDraftRestorePrompt(draft, editor);
	}
	
	// Start autosave
	startAutosave(editor);

	// new post
	$("#submit_btn").click(function (event) {
		// get editor content
		var elContent =
			editor.serialize()[Object.keys(editor.serialize())[0]].value;
		if (elContent.length == "0") {
			console.log("no text");
			return;
		}

		// Check for blob URLs - if found, alert user to wait for uploads
		if (contentHasBlobUrls(elContent)) {
			alert("Please wait for image uploads to complete before saving.");
			return;
		}

		elContent = cleanContent(elContent);
		var hashtags = getHashtag(elContent)[0];
		elContent = linkify(elContent);
		elContent = elContent.replaceAll(' class="hashtag"', "");
		var post_date = getFormattedDate();

		var status = "public";
		var author = $("#site").attr("author");
		var icon = $("#site").attr("author_image");
		var author_name = $("#site").attr("author_name");
		var link = "/";

		var poststring = makePostString(
			post_date,
			hashtags,
			status,
			author,
			author_name,
			link,
			icon,
			elContent
		);
		var text = poststring[0];
		var title = poststring[1];

		var post_filename = strip(title).substring(0, filename_maxlength);
		post_filename = slugify(post_filename);
		// if no filename found, make random name
		if (post_filename.length <= 1) {
			post_filename = makeid(8);
		}
		post_filename = "" + getDateForFilename() + post_filename;

		// submit
		$.ajax({
			url: "/post",
			data: { text: text, path: post_filename, unique: true },
			type: "POST",
			success: function (response) {
				// Clear autosaved draft on successful post
				clearDraft();
				stopAutosave();
				location.reload();
			},
			error: function (error) {
				console.log(error);
			},
		});
	});

	function pollPublishingStatus() {
		$.ajax({
			url: "/publishing-status",
			type: "GET",
			success: function (response) {
				if (response.status === "publishing") {
					$(".note_publish")
						.html(
							'<b>Publishing</b> <img style="margin-bottom:-4px;" src="/static/img/loading.gif" width="15"/><br/>' +
								response.text
						)
						.slideDown("fast");
					setTimeout(pollPublishingStatus, 1000);
				} else if (response.status === "done") {
					var url_site = $("#site").attr("site");
					var url_display = truncate(url_site, 21);
					$(".note_publish")
						.html(
							'<b>Published to</b><br/><a href="' +
								url_site +
								'" target="_blank">' +
								url_display +
								"</a>"
						)
						.delay(3500)
						.slideUp("fast");
					$("#btn_publish").prop("disabled", false).removeClass("btn_disabled");
				} else if (response.status === "error") {
					$(".note_publish")
						.html("<b>ERROR publishing:</b><br/>" + response.text)
						.delay(3500)
						.slideUp("fast");
					$("#btn_publish").prop("disabled", false).removeClass("btn_disabled");
				}
			},
			error: function (error) {
				console.log(error);
				$(".note_publish")
					.html("<b>ERROR checking publishing status</b>")
					.delay(3500)
					.slideUp("fast");
				$("#btn_publish").prop("disabled", false).removeClass("btn_disabled");
			},
		});
	}

	$("#btn_publish").click(function (event) {
		event.preventDefault();
		$("#btn_publish").prop("disabled", true).addClass("btn_disabled");
		$(".note_publish")
			.html(
				'<b>Publishing</b> <img style="margin-bottom:-4px;" src="/static/img/loading.gif" width="15"/><br/>Generating Site'
			)
			.slideDown("fast");

		$.ajax({
			url: "/publish",
			type: "POST",
			success: function (response) {
				// console.log(response);
				pollPublishingStatus();
			},
			error: function (error) {
				console.log(error);
				$("#btn_publish").prop("disabled", false).removeClass("btn_disabled");
				$(".note_publish")
					.html("<b>ERROR starting publishing</b>")
					.delay(3500)
					.slideUp("fast");
			},
		});
	});
}

function setup() {
	// submit search
	$("#search_form").submit(function (event) {
		var text = $("#search_input").val();
		event.preventDefault();
		window.location.href = "/search/?q=" + encodeURIComponent(text);
	});
	// mark text when searching
	if (window.location.href.indexOf("search") > -1) {
		var url_string = window.location.href;
		var url = new URL(url_string);
		var q = url.searchParams.get("q");
		if (q != null) {
			$(".content_main").mark(q);
		}
	}
}

// Tag Autocomplete functionality
function initTagAutocomplete() {
	// Create autocomplete container if it doesn't exist
	if (!document.getElementById('tag-autocomplete')) {
		const autocompleteDiv = document.createElement('div');
		autocompleteDiv.id = 'tag-autocomplete';
		autocompleteDiv.className = 'tag-autocomplete-container';
		autocompleteDiv.style.cssText = `
			display: none;
			position: absolute;
			background: white;
			border: 1px solid #ddd;
			border-radius: 8px;
			box-shadow: 0 4px 12px rgba(0,0,0,0.15);
			max-height: 200px;
			overflow-y: auto;
			z-index: 10000;
			min-width: 180px;
		`;
		document.body.appendChild(autocompleteDiv);
	}

	// Fetch tags if not cached
	if (!cachedTags) {
		fetch('/api/tags')
			.then(response => response.json())
			.then(tags => {
				cachedTags = tags;
			})
			.catch(err => console.log('Could not load tags for autocomplete'));
	}
}

function showTagAutocomplete(editorElement, searchTerm) {
	const autocomplete = document.getElementById('tag-autocomplete');
	if (!autocomplete || !cachedTags) return;

	// Filter tags based on search term
	const filtered = cachedTags.filter(tag => 
		tag.name.toLowerCase().includes(searchTerm.toLowerCase())
	).slice(0, 10); // Limit to 10 suggestions

	if (filtered.length === 0) {
		autocomplete.style.display = 'none';
		return;
	}

	// Build suggestion HTML
	autocomplete.innerHTML = filtered.map(tag => `
		<div class="tag-suggestion" data-tag="${tag.name}" style="
			padding: 10px 14px;
			cursor: pointer;
			border-bottom: 1px solid #f0f0f0;
			display: flex;
			justify-content: space-between;
			align-items: center;
		">
			<span style="font-weight: 500;">#${tag.name}</span>
			<span style="color: #999; font-size: 12px;">${tag.count} posts</span>
		</div>
	`).join('');

	// Position autocomplete near cursor
	const selection = window.getSelection();
	if (selection.rangeCount > 0) {
		const range = selection.getRangeAt(0);
		const rect = range.getBoundingClientRect();
		// Add scroll offset for correct positioning
		const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
		const scrollY = window.pageYOffset || document.documentElement.scrollTop;
		autocomplete.style.left = (rect.left + scrollX) + 'px';
		autocomplete.style.top = (rect.bottom + scrollY + 5) + 'px';
	}

	autocomplete.style.display = 'block';

	// Add hover effect
	autocomplete.querySelectorAll('.tag-suggestion').forEach(el => {
		el.addEventListener('mouseenter', function() {
			this.style.backgroundColor = '#f5f5f5';
		});
		el.addEventListener('mouseleave', function() {
			this.style.backgroundColor = 'white';
		});
	});

	// Handle click on suggestion (use mousedown to prevent editor blur)
	autocomplete.querySelectorAll('.tag-suggestion').forEach(el => {
		el.addEventListener('mousedown', function(e) {
			e.preventDefault(); // Prevent editor from losing focus
			e.stopPropagation();
			const tagName = this.dataset.tag;
			insertTagAtCursor(tagName, searchTerm);
			autocomplete.style.display = 'none';
		});
	});
}

function insertTagAtCursor(tagName, searchTerm) {
	const selection = window.getSelection();
	if (selection.rangeCount > 0) {
		const range = selection.getRangeAt(0);
		
		// Find and delete the partial hashtag the user typed
		const textNode = range.startContainer;
		if (textNode.nodeType === Node.TEXT_NODE) {
			const text = textNode.textContent;
			const cursorPos = range.startOffset;
			
			// Find the # before cursor
			let hashPos = text.lastIndexOf('#', cursorPos - 1);
			if (hashPos !== -1) {
				// Replace from # to cursor with the complete tag
				const before = text.substring(0, hashPos);
				const after = text.substring(cursorPos);
				textNode.textContent = before + '#' + tagName + ' ' + after;
				
				// Move cursor to end of inserted tag
				const newPos = hashPos + tagName.length + 2; // +2 for # and space
				range.setStart(textNode, newPos);
				range.setEnd(textNode, newPos);
				selection.removeAllRanges();
				selection.addRange(range);
			}
		}
	}
}

function hideTagAutocomplete() {
	const autocomplete = document.getElementById('tag-autocomplete');
	if (autocomplete) {
		autocomplete.style.display = 'none';
	}
}

function setupTagAutocompleteForEditor(editorElement) {
	let currentHashtagSearch = '';
	let isTypingHashtag = false;

	$(editorElement).on('input', function(e) {
		const selection = window.getSelection();
		if (selection.rangeCount === 0) return;

		const range = selection.getRangeAt(0);
		const textNode = range.startContainer;
		
		if (textNode.nodeType !== Node.TEXT_NODE) {
			hideTagAutocomplete();
			return;
		}

		const text = textNode.textContent;
		const cursorPos = range.startOffset;
		
		// Find if we're typing a hashtag (look backwards for #)
		let hashPos = -1;
		for (let i = cursorPos - 1; i >= 0; i--) {
			if (text[i] === '#') {
				hashPos = i;
				break;
			} else if (text[i] === ' ' || text[i] === '\n') {
				break;
			}
		}

		if (hashPos !== -1) {
			const searchTerm = text.substring(hashPos + 1, cursorPos);
			if (searchTerm.length >= 1) {
				isTypingHashtag = true;
				currentHashtagSearch = searchTerm;
				showTagAutocomplete(editorElement, searchTerm);
			} else {
				hideTagAutocomplete();
			}
		} else {
			isTypingHashtag = false;
			hideTagAutocomplete();
		}
	});

	// Hide autocomplete when clicking outside
	$(document).on('click', function(e) {
		if (!$(e.target).closest('#tag-autocomplete').length) {
			hideTagAutocomplete();
		}
	});

	// Handle keyboard navigation in autocomplete
	$(editorElement).on('keydown', function(e) {
		const autocomplete = document.getElementById('tag-autocomplete');
		if (!autocomplete || autocomplete.style.display === 'none') return;

		const suggestions = autocomplete.querySelectorAll('.tag-suggestion');
		if (suggestions.length === 0) return;

		let currentIndex = -1;
		suggestions.forEach((el, i) => {
			if (el.style.backgroundColor === 'rgb(245, 245, 245)') {
				currentIndex = i;
			}
		});

		if (e.key === 'ArrowDown') {
			e.preventDefault();
			suggestions.forEach(el => el.style.backgroundColor = 'white');
			const nextIndex = (currentIndex + 1) % suggestions.length;
			suggestions[nextIndex].style.backgroundColor = '#f5f5f5';
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			suggestions.forEach(el => el.style.backgroundColor = 'white');
			const prevIndex = currentIndex <= 0 ? suggestions.length - 1 : currentIndex - 1;
			suggestions[prevIndex].style.backgroundColor = '#f5f5f5';
		} else if (e.key === 'Enter' || e.key === 'Tab') {
			const selected = autocomplete.querySelector('.tag-suggestion[style*="rgb(245, 245, 245)"]');
			if (selected) {
				e.preventDefault();
				const tagName = selected.dataset.tag;
				insertTagAtCursor(tagName, currentHashtagSearch);
				hideTagAutocomplete();
			}
		} else if (e.key === 'Escape') {
			hideTagAutocomplete();
		}
	});
}

// ============================================
// Related Posts Panel
// ============================================

// Common stop words to filter out when extracting keywords
const STOP_WORDS = new Set([
	'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
	'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
	'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
	'shall', 'can', 'need', 'dare', 'ought', 'used', 'i', 'you', 'he', 'she', 'it',
	'we', 'they', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
	'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
	'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
	'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about',
	'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
	'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under',
	'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
	'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
	'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just',
	'don', 'should', 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', 'couldn',
	'didn', 'doesn', 'hadn', 'hasn', 'haven', 'isn', 'ma', 'mightn', 'mustn', 'needn',
	'shan', 'shouldn', 'wasn', 'weren', 'won', 'wouldn', 'im', 'ive', 'id', 'youre',
	'its', 'thats', 'whats', 'heres', 'theres', 'whos', 'lets', 'get', 'got', 'getting',
	'going', 'go', 'goes', 'went', 'come', 'came', 'coming', 'make', 'made', 'making',
	'see', 'saw', 'seen', 'seeing', 'know', 'knew', 'known', 'knowing', 'think', 'thought',
	'thinking', 'take', 'took', 'taken', 'taking', 'want', 'wanted', 'wanting', 'use',
	'using', 'find', 'found', 'finding', 'give', 'gave', 'given', 'giving', 'tell', 'told',
	'telling', 'work', 'worked', 'working', 'seem', 'seemed', 'seeming', 'feel', 'felt',
	'feeling', 'try', 'tried', 'trying', 'leave', 'left', 'leaving', 'call', 'called',
	'calling', 'keep', 'kept', 'keeping', 'let', 'letting', 'begin', 'began', 'begun',
	'beginning', 'show', 'showed', 'shown', 'showing', 'hear', 'heard', 'hearing', 'play',
	'played', 'playing', 'run', 'ran', 'running', 'move', 'moved', 'moving', 'like',
	'liked', 'liking', 'live', 'lived', 'living', 'believe', 'believed', 'believing',
	'hold', 'held', 'holding', 'bring', 'brought', 'bringing', 'happen', 'happened',
	'happening', 'write', 'wrote', 'written', 'writing', 'provide', 'provided', 'providing',
	'sit', 'sat', 'sitting', 'stand', 'stood', 'standing', 'lose', 'lost', 'losing',
	'pay', 'paid', 'paying', 'meet', 'met', 'meeting', 'include', 'included', 'including',
	'continue', 'continued', 'continuing', 'set', 'setting', 'learn', 'learned', 'learning',
	'change', 'changed', 'changing', 'lead', 'led', 'leading', 'understand', 'understood',
	'understanding', 'watch', 'watched', 'watching', 'follow', 'followed', 'following',
	'stop', 'stopped', 'stopping', 'create', 'created', 'creating', 'speak', 'spoke',
	'spoken', 'speaking', 'read', 'reading', 'allow', 'allowed', 'allowing', 'add',
	'added', 'adding', 'spend', 'spent', 'spending', 'grow', 'grew', 'grown', 'growing',
	'open', 'opened', 'opening', 'walk', 'walked', 'walking', 'win', 'won', 'winning',
	'offer', 'offered', 'offering', 'remember', 'remembered', 'remembering', 'love',
	'loved', 'loving', 'consider', 'considered', 'considering', 'appear', 'appeared',
	'appearing', 'buy', 'bought', 'buying', 'wait', 'waited', 'waiting', 'serve', 'served',
	'serving', 'die', 'died', 'dying', 'send', 'sent', 'sending', 'expect', 'expected',
	'expecting', 'build', 'built', 'building', 'stay', 'stayed', 'staying', 'fall', 'fell',
	'fallen', 'falling', 'cut', 'cutting', 'reach', 'reached', 'reaching', 'kill', 'killed',
	'killing', 'remain', 'remained', 'remaining', 'really', 'maybe', 'also', 'still', 'even',
	'back', 'well', 'way', 'look', 'first', 'also', 'new', 'because', 'day', 'more', 'use',
	'man', 'many', 'way', 'each', 'much', 'before', 'two', 'long', 'very', 'thing'
]);

function extractKeywordsAndTags(content) {
	// Extract hashtags
	const hashtagRegex = /#(\w+)/g;
	const tags = [];
	let match;
	while ((match = hashtagRegex.exec(content)) !== null) {
		tags.push(match[1].toLowerCase());
	}
	
	// Remove HTML and extract text
	const text = content
		.replace(/<[^>]*>/g, ' ')  // Strip HTML
		.replace(/https?:\/\/\S+/g, '')  // Strip URLs
		.replace(/#\w+/g, '')  // Remove hashtags (already extracted)
		.replace(/[^\w\s]/g, ' ')  // Remove punctuation
		.toLowerCase();
	
	// Extract significant words
	const words = text.split(/\s+/)
		.filter(word => word.length > 3)  // Only words > 3 chars
		.filter(word => !STOP_WORDS.has(word))  // Remove stop words
		.filter(word => !/^\d+$/.test(word));  // Remove pure numbers
	
	// Count word frequency
	const wordFreq = {};
	words.forEach(word => {
		wordFreq[word] = (wordFreq[word] || 0) + 1;
	});
	
	// Sort by frequency and take top keywords
	const keywords = Object.entries(wordFreq)
		.sort((a, b) => b[1] - a[1])
		.slice(0, 5)
		.map(([word]) => word);
	
	return { keywords, tags: [...new Set(tags)] };  // Dedupe tags
}

let relatedPanelOpen = false;
let currentRelatedOffset = 0;
let isLoadingRelated = false;
let currentQuery = '';
let currentTags = '';

function openRelatedPanel() {
	const panel = document.getElementById('related_panel');
	if (!panel) return;
	
	// Get editor content
	const editorContent = $('#text_area').html() || '';
	if (!editorContent.trim()) return;
	
	// Extract keywords and tags
	const { keywords, tags } = extractKeywordsAndTags(editorContent);
	currentQuery = keywords.join(' ');
	currentTags = tags.join(',');
	
	// Reset state
	currentRelatedOffset = 0;
	relatedPanelOpen = true;
	
	// Show panel
	panel.classList.remove('related-panel-hidden');
	
	// Load initial results
	loadRelatedPosts(true);
}

function closeRelatedPanel() {
	const panel = document.getElementById('related_panel');
	if (panel) {
		panel.classList.add('related-panel-hidden');
	}
	relatedPanelOpen = false;
}

function loadRelatedPosts(isInitial = false) {
	if (isLoadingRelated) return;
	
	const resultsContainer = document.getElementById('related_results');
	if (!resultsContainer) return;
	
	isLoadingRelated = true;
	
	if (isInitial) {
		resultsContainer.innerHTML = '<div class="related-loading"><img src="/static/img/loading.gif" alt="Loading..." width="40" /></div>';
	}
	
	// Build API URL
	const params = new URLSearchParams();
	if (currentQuery) params.set('q', currentQuery);
	if (currentTags) params.set('tags', currentTags);
	params.set('offset', currentRelatedOffset);
	params.set('limit', 15);
	
	fetch('/api/related?' + params.toString())
		.then(response => response.text())
		.then(html => {
			const tempDiv = document.createElement('div');
			tempDiv.innerHTML = html;
			
			const content = tempDiv.querySelector('.related-posts-content');
			if (!content) {
				isLoadingRelated = false;
				return;
			}
			
			const hasMore = content.dataset.hasMore === 'true';
			const nextOffset = parseInt(content.dataset.nextOffset) || 0;
			const totalResults = parseInt(content.dataset.total) || 0;
			
			// Update count display
			const countEl = document.getElementById('related_count');
			if (countEl) {
				countEl.textContent = totalResults > 0 ? `(${totalResults} found)` : '';
			}
			
			if (isInitial) {
				resultsContainer.innerHTML = content.innerHTML;
			} else {
				// Append new results
				resultsContainer.insertAdjacentHTML('beforeend', content.innerHTML);
				// Remove old "load more" button if exists
				const oldLoadMore = resultsContainer.querySelector('.related-load-more');
				if (oldLoadMore) oldLoadMore.remove();
			}
			
			// Add load more button if there are more results
			if (hasMore) {
				currentRelatedOffset = nextOffset;
				const loadMoreDiv = document.createElement('div');
				loadMoreDiv.className = 'related-load-more';
				loadMoreDiv.innerHTML = '<button class="related-load-more-btn">Load more posts...</button>';
				loadMoreDiv.querySelector('button').addEventListener('click', () => loadRelatedPosts(false));
				resultsContainer.appendChild(loadMoreDiv);
			}
			
			// Setup insert buttons for new items
			setupRelatedInsertButtons();
			
			// Format dates in the new content
			if (typeof formatDate === 'function') {
				formatDate();
			}
			
			// Apply content height formatting
			resultsContainer.querySelectorAll('.related-post-content').forEach(el => {
				if (el.offsetHeight > 200) {
					el.style.maxHeight = '200px';
					el.style.overflow = 'hidden';
				}
			});
			
			isLoadingRelated = false;
		})
		.catch(err => {
			console.error('Error loading related posts:', err);
			if (isInitial) {
				resultsContainer.innerHTML = '<div class="related-empty"><p>Error loading related posts.</p></div>';
			}
			isLoadingRelated = false;
		});
}

function setupRelatedInsertButtons() {
	document.querySelectorAll('.related-insert-btn').forEach(btn => {
		if (btn.dataset.listenerAttached) return;
		btn.dataset.listenerAttached = 'true';
		
		btn.addEventListener('click', function(e) {
			e.preventDefault();
			e.stopPropagation();
			
			const postItem = this.closest('.related-post-item');
			if (!postItem) return;
			
			const url = postItem.dataset.url;
			
			// Create flow-embed element for quote card
			const embedHtml = `<flow-embed url="${url}"></flow-embed>`;
			
			// Insert into editor
			insertEmbedIntoEditor(embedHtml);
			
			// Visual feedback
			const originalText = this.innerHTML;
			this.innerHTML = '✓ Inserted';
			this.style.background = '#28a54f';
			setTimeout(() => {
				this.innerHTML = originalText;
				this.style.background = '';
			}, 1500);
		});
	});
}

function insertLinkIntoEditor(link) {
	const editor = document.getElementById('text_area');
	if (!editor) return;
	
	// Focus the editor
	editor.focus();
	
	// Insert at cursor position or at end
	const selection = window.getSelection();
	
	if (selection.rangeCount > 0) {
		const range = selection.getRangeAt(0);
		
		// Check if cursor is inside the editor
		if (editor.contains(range.commonAncestorContainer)) {
			// Insert at cursor
			const textNode = document.createTextNode(' ' + link + ' ');
			range.insertNode(textNode);
			range.setStartAfter(textNode);
			range.setEndAfter(textNode);
			selection.removeAllRanges();
			selection.addRange(range);
		} else {
			// Append to end
			appendLinkToEditor(editor, link);
		}
	} else {
		// Append to end
		appendLinkToEditor(editor, link);
	}
	
	// Trigger input event to update state
	editor.dispatchEvent(new Event('input', { bubbles: true }));
}

function insertEmbedIntoEditor(embedHtml) {
	const editor = document.getElementById('text_area');
	if (!editor) return;
	
	// Focus the editor
	editor.focus();
	
	// Create a container for the embed
	const container = document.createElement('div');
	container.innerHTML = embedHtml;
	const embedElement = container.firstChild;
	
	// We want to insert the embed as a block element
	// Add a paragraph wrapper with the embed and a line break after
	const wrapper = document.createElement('p');
	wrapper.appendChild(embedElement);
	
	// Find where to insert
	const selection = window.getSelection();
	
	if (selection.rangeCount > 0) {
		const range = selection.getRangeAt(0);
		
		// Check if cursor is inside the editor
		if (editor.contains(range.commonAncestorContainer)) {
			// Insert after current paragraph
			let currentP = range.commonAncestorContainer;
			while (currentP && currentP.tagName !== 'P' && currentP !== editor) {
				currentP = currentP.parentNode;
			}
			
			if (currentP && currentP.tagName === 'P') {
				currentP.parentNode.insertBefore(wrapper, currentP.nextSibling);
			} else {
				editor.appendChild(wrapper);
			}
		} else {
			editor.appendChild(wrapper);
		}
	} else {
		editor.appendChild(wrapper);
	}
	
	// Add an empty paragraph after for continued typing
	const newP = document.createElement('p');
	newP.innerHTML = '<br>';
	wrapper.parentNode.insertBefore(newP, wrapper.nextSibling);
	
	// Move cursor to the new paragraph
	const newRange = document.createRange();
	newRange.setStart(newP, 0);
	newRange.collapse(true);
	selection.removeAllRanges();
	selection.addRange(newRange);
	
	// Trigger input event to update state
	editor.dispatchEvent(new Event('input', { bubbles: true }));
	
	// Initialize the flow-embed rendering
	if (typeof window.initFlowEmbeds === 'function') {
		window.initFlowEmbeds();
	}
}

function appendLinkToEditor(editor, link) {
	// Find or create last paragraph
	let lastP = editor.querySelector('p:last-of-type');
	if (!lastP) {
		lastP = document.createElement('p');
		editor.appendChild(lastP);
	}
	
	// Add a space and the link
	if (lastP.textContent.trim()) {
		lastP.appendChild(document.createTextNode(' '));
	}
	lastP.appendChild(document.createTextNode(link));
}

function initRelatedPanel() {
	// Button click handler
	const relatedBtn = document.getElementById('related_btn');
	if (relatedBtn) {
		relatedBtn.addEventListener('click', openRelatedPanel);
	}
	
	// Close button handler
	const closeBtn = document.getElementById('related_close');
	if (closeBtn) {
		closeBtn.addEventListener('click', closeRelatedPanel);
	}
	
	// Keyboard shortcut: Cmd/Ctrl + Shift + R
	document.addEventListener('keydown', function(e) {
		if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'r') {
			e.preventDefault();
			if (relatedPanelOpen) {
				closeRelatedPanel();
			} else {
				openRelatedPanel();
			}
		}
		
		// Escape to close
		if (e.key === 'Escape' && relatedPanelOpen) {
			closeRelatedPanel();
		}
	});
	
	// Infinite scroll in panel
	const resultsContainer = document.getElementById('related_results');
	if (resultsContainer) {
		resultsContainer.addEventListener('scroll', function() {
			if (isLoadingRelated) return;
			
			const scrollBottom = this.scrollTop + this.clientHeight;
			const scrollHeight = this.scrollHeight;
			
			// Load more when near bottom
			if (scrollHeight - scrollBottom < 200) {
				const loadMoreBtn = this.querySelector('.related-load-more-btn');
				if (loadMoreBtn) {
					loadMoreBtn.click();
				}
			}
		});
	}
}

// run all
$(function () {
	initTagAutocomplete();
	initRelatedPanel();
	newpost();
	editpost();
	setup();

	$("#text_area").focus();
	setTimeout(function () {
		$("#text_area").focus();
	}, 10);
});
