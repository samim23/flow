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
	return (elContent = linkifyHtml(elContent, {
		nl2br: false, // optional
		formatHref: {
			hashtag: (href) => `/tag/${href.replace("#", "")}`,
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

	var tempDom = $("<output>").append($.parseHTML(elContent));
	// tempDom.find('*').removeAttr('style');
	tempDom.find("a").removeAttr("style");
	tempDom.find("p").removeAttr("style");
	tempDom.find("span").removeAttr("style");
	tempDom.find("blockquote").removeAttr("style");
	tempDom.find("a").removeAttr("class");
	tempDom.find("img").removeAttr("data-gallery-initialized");
	tempDom.find(".medium-insert-buttons").remove();
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
		editor: editor, // (MediumEditor) Instance of MediumEditor
		enabled: true, // (boolean) If the plugin is enabled
		addons: {
			// (object) Addons configuration
			images: {
				label: '<span class="fa fa-camera"></span>',
				deleteScript: null,
				deleteMethod: "POST",
				fileDeleteOptions: {},
				preview: true,
				captions: true,
				captionPlaceholder: "Type caption for image (optional)",
				autoGrid: 2,
				styles: {
					wide: {
						label: '<span class="fa fa-align-justify"></span>',
						added: function ($el) {},
						removed: function ($el) {},
					},
					left: {
						label: '<span class="fa fa-align-left"></span>',
					},
					right: {
						label: '<span class="fa fa-align-right"></span>',
					},
					grid: {
						label: '<span class="fa fa-th"></span>',
					},
				},
				actions: {
					remove: {
						label: '<span class="fa fa-times"></span>',
						clicked: function ($el) {
							var $event = $.Event("keydown");
							$event.which = 8;
							$(document).trigger($event);
						},
					},
				},
				messages: {
					acceptFileTypesError: "This file is not in a supported format: ",
					maxFileSizeError: "This file is too big: ",
				},
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
			$(".note_publish").slideUp("fast"); // Ensure indicator is hidden
		} else {
			submit_btn.hide();
		}
	});
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
	// Ensure title sanitization is left unchanged
	let title = elContent.trim(); // Original sanitization logic follows
	title = title.replace(/<[^>]*>?/gm, ""); // strip HTML
	title = title.replace(/(?:https?|ftp):\/\/[\n\S]+/g, ""); // strip links
	title = title.replace(/\#/g, ""); // remove hashtags symbol
	title = title.replace(/\n\s*\n/g, "\n"); // replace multi line breaks with single
	title = title.replace(/\n/g, ". "); // replace line breaks with dot
	title = title.replace(/\r\n|\n|\r/gm, ""); // remove double spaces
	title = title.replace(/\s+/g, " "); // remove extra spaces
	title = title.replace(/:/g, " -"); // replace colons
	title = title.replace(/['"“”]/g, ""); // remove quotes
	title = title.trim() || "Untitled"; // Default to "Untitled" if empty

	title = truncate(title, 70); // Trunacate title

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
				editing = false;
				post_edit.removeClass(".editable");
				$(".content_btn").remove();

				// get editor content
				var allContents = editor2.serialize();
				var elContent = allContents["element-0"].value;

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

function newpost() {
	var editor = editor_create($(".editable"), $("#submit_btn"));

	// new post
	$("#submit_btn").click(function (event) {
		// get editor content
		var elContent =
			editor.serialize()[Object.keys(editor.serialize())[0]].value;
		if (elContent.length == "0") {
			console.log("no text");
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
				// console.log(response);
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
		window.location.href = "/search/?q=" + text;
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

// run all
$(function () {
	newpost();
	editpost();
	setup();

	$("#text_area").focus();
	setTimeout(function () {
		$("#text_area").focus();
	}, 10);
});
