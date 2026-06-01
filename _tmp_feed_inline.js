
if (!localStorage.getItem("loggedIn")) {
    window.location.href = "index.html";
}

function logout() {
    localStorage.removeItem("loggedIn");
    localStorage.removeItem("username");
    window.location.href = "index.html";
}
    


document.addEventListener("DOMContentLoaded", () => {
    const API_BASE = "http://127.0.0.1:8000";
    const CURRENT_USER = (localStorage.getItem("username") || "_theertha_").trim() || "_theertha_";
    let CURRENT_FEED_MODE = "all";
    localStorage.setItem("username", CURRENT_USER);

    const openUpload = document.getElementById("openUpload");
    const uploadModal = document.getElementById("uploadModal");
    const closeModal = document.getElementById("closeModal");
    const createBtn = document.getElementById("createBtn");
    const imageInput = document.getElementById("imageInput");
    const previewImage = document.getElementById("previewImage");
    const uploadBtn = document.getElementById("uploadBtn");
    const hideToggle = document.getElementById("hideToggle");
    const stegoStrictToggle = document.getElementById("stegoStrictToggle");
    const captionInput = document.getElementById("captionInput");
    const visibilityInput = document.getElementById("visibilityInput");
    const manualBlurInput = document.getElementById("manualBlurInput");
    const feed = document.getElementById("feed");
    const searchInput = document.getElementById("searchInput");
    const searchBtn = document.getElementById("searchBtn");
    const searchResults = document.getElementById("searchResults");
    const notificationList = document.getElementById("notificationList");
    const savedPostsList = document.getElementById("savedPostsList");
    const moderationList = document.getElementById("moderationList");
    const stegoHistoryList = document.getElementById("stegoHistoryList");
    const messagePeerInput = document.getElementById("messagePeerInput");
    const messageInput = document.getElementById("messageInput");
    const sendMessageBtn = document.getElementById("sendMessageBtn");
    const messageList = document.getElementById("messageList");
    const profileAvatarPreview = document.getElementById("profileAvatarPreview");
    const navProfileAvatar = document.getElementById("navProfileAvatar");
    const sidebarUsername = document.getElementById("sidebarUsername");
    const sidebarFullName = document.getElementById("sidebarFullName");
    const sidebarBio = document.getElementById("sidebarBio");
    const postsCount = document.getElementById("postsCount");
    const followersCount = document.getElementById("followersCount");
    const followingCount = document.getElementById("followingCount");
    const profileFullNameInput = document.getElementById("profileFullNameInput");
    const profileBioInput = document.getElementById("profileBioInput");
    const profileAvatarInput = document.getElementById("profileAvatarInput");
    const privateAccountInput = document.getElementById("privateAccountInput");
    const profileVisibilityInput = document.getElementById("profileVisibilityInput");
    const messagePrivacyInput = document.getElementById("messagePrivacyInput");
    const commentPrivacyInput = document.getElementById("commentPrivacyInput");
    const activityStatusInput = document.getElementById("activityStatusInput");
    const readReceiptsInput = document.getElementById("readReceiptsInput");
    const tagApprovalInput = document.getElementById("tagApprovalInput");
    const saveProfileBtn = document.getElementById("saveProfileBtn");
    const followRequestsList = document.getElementById("followRequestsList");
    const tagRequestsList = document.getElementById("tagRequestsList");
    const privacyTargetInput = document.getElementById("privacyTargetInput");
    const blockUserBtn = document.getElementById("blockUserBtn");
    const closeFriendBtn = document.getElementById("closeFriendBtn");
    const blockedUsersList = document.getElementById("blockedUsersList");
    const closeFriendsList = document.getElementById("closeFriendsList");
    const privacyRelationsStatus = document.getElementById("privacyRelationsStatus");
    const markNotificationsReadBtn = document.getElementById("markNotificationsReadBtn");
    const loadSavedBtn = document.getElementById("loadSavedBtn");
    const allFeedBtn = document.getElementById("allFeedBtn");
    const followingFeedBtn = document.getElementById("followingFeedBtn");
    const feedStatusLabel = document.getElementById("feedStatusLabel");
    const darkModeToggle = document.getElementById("darkModeToggle");
    const heroCreateBtn = document.getElementById("heroCreateBtn");
    const heroPostsCount = document.getElementById("heroPostsCount");
    const heroFollowersCount = document.getElementById("heroFollowersCount");
    const heroFollowingCount = document.getElementById("heroFollowingCount");
    const searchStatus = document.getElementById("searchStatus");
    const messageStatus = document.getElementById("messageStatus");
    const profileStatus = document.getElementById("profileStatus");
    const composerStatus = document.getElementById("composerStatus");

    const SUPPORTED_MIME_TYPES = new Set([
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/bmp",
        "image/tiff",
        "image/webp",
    ]);
    const SUPPORTED_EXTENSIONS = new Set(["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"]);

    const isSupportedImage = (file) => {
        if (!file) return false;
        const type = (file.type || "").toLowerCase();
        if (SUPPORTED_MIME_TYPES.has(type)) return true;
        const name = (file.name || "").toLowerCase();
        const ext = name.includes(".") ? name.split(".").pop() : "";
        return SUPPORTED_EXTENSIONS.has(ext);
    };

    const escapeHtml = (value) => {
        const div = document.createElement("div");
        div.innerText = value ?? "";
        return div.innerHTML;
    };

    const createPanelItem = (title, subtitle, extraStyle = "") => `<div class="panel-item" style="${extraStyle}"><strong>${title}</strong><small>${subtitle}</small></div>`;
    const createRequestItem = (username) => `<div class="panel-item"><strong>${escapeHtml(username)}</strong><small>Pending follow request</small><div class="feature-actions"><button class="feature-btn primary followRequestActionBtn" data-action="approve" data-username="${escapeHtml(username)}" type="button">Approve</button><button class="feature-btn secondary followRequestActionBtn" data-action="reject" data-username="${escapeHtml(username)}" type="button">Reject</button></div></div>`;
    const createTagRequestItem = (row) => `<div class="panel-item"><strong>${escapeHtml(row.requester_username || "Unknown")}</strong><small>Tagged you in a post</small>${row.caption_preview ? `<small>${escapeHtml(row.caption_preview)}</small>` : ""}<div class="feature-actions"><button class="feature-btn primary tagRequestActionBtn" data-action="approve" data-post-id="${row.post_id}" type="button">Approve</button><button class="feature-btn secondary tagRequestActionBtn" data-action="reject" data-post-id="${row.post_id}" type="button">Hide</button></div></div>`;
    const createCommentMarkup = (comment) => `<p><strong>${escapeHtml(comment.username || "user")}:</strong> ${escapeHtml(comment.content || "")}</p>`;
    const getLikeText = (count) => !count ? "Liked by others" : count === 1 ? "1 like" : `${count} likes`;
    const renderRiskReport = (riskReport) => {
        if (!riskReport) return "";
        const parts = [];
        if (riskReport.license_plate_blurs) parts.push(`${riskReport.license_plate_blurs} license plate blur${riskReport.license_plate_blurs === 1 ? "" : "s"}`);
        if (riskReport.aadhaar_blurs) parts.push(`${riskReport.aadhaar_blurs} Aadhaar blur${riskReport.aadhaar_blurs === 1 ? "" : "s"}`);
        if (riskReport.card_blurs) parts.push(`${riskReport.card_blurs} card blur${riskReport.card_blurs === 1 ? "" : "s"}`);
        if (riskReport.manual_blur_regions) parts.push(`${riskReport.manual_blur_regions} manual blur${riskReport.manual_blur_regions === 1 ? "" : "s"}`);
        const message = parts.length ? `Protected: ${parts.join(", ")}.` : (riskReport.reason || riskReport.message || "Processed");
        return `<p class="riskText">${escapeHtml(message)}</p>`;
    };
    const updateLikeButton = (icon, liked) => { icon.classList.toggle("fa-solid", liked); icon.classList.toggle("fa-regular", !liked); icon.style.color = liked ? "#ed4956" : ""; icon.dataset.liked = liked ? "1" : "0"; };
    const updateSaveButton = (icon, saved) => { icon.classList.toggle("fa-solid", saved); icon.classList.toggle("fa-regular", !saved); icon.dataset.saved = saved ? "1" : "0"; };
    const formatCaption = (text) => escapeHtml(text).replace(/(^|\\s)#([a-zA-Z0-9_]+)/g, '$1<a href="#" class="tagLink" data-tag="$2">#$2</a>').replace(/(^|\\s)@([a-zA-Z0-9_.]+)/g, '$1<a href="#" class="mentionLink" data-user="$2">@$2</a>');
    const setStatus = (element, message, kind = "") => {
        if (!element) return;
        element.className = `status-note${kind ? ` ${kind}` : ""}`;
        element.innerText = message;
    };

    function renderSearchResults(data) {
        const sections = [];
        if (data.users?.length) sections.push(data.users.map((user) => createPanelItem(escapeHtml(user.username), escapeHtml(user.full_name || "User"))).join(""));
        if (data.posts?.length) sections.push(data.posts.map((post) => createPanelItem(escapeHtml(post.username), escapeHtml(post.caption_public || post.caption || "Post"))).join(""));
        if (data.comments?.length) sections.push(data.comments.map((comment) => createPanelItem(escapeHtml(comment.username || "Comment"), escapeHtml(comment.content || ""))).join(""));
        const resultCount = (data.users?.length || 0) + (data.posts?.length || 0) + (data.comments?.length || 0);
        setStatus(searchStatus, resultCount ? `Found ${resultCount} result${resultCount === 1 ? "" : "s"}.` : "No matches found.", resultCount ? "success" : "");
        searchResults.innerHTML = sections.length ? sections.join("") : `<div class="panel-empty">No matches found.</div>`;
    }

    async function loadPrivacyOverview() {
        try {
            const response = await fetch(`${API_BASE}/privacy/overview?username=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            const data = await response.json();
            const privacy = data.privacy || {};
            privateAccountInput.checked = Boolean(privacy.is_private);
            profileVisibilityInput.value = privacy.profile_visibility || "public";
            messagePrivacyInput.value = privacy.message_privacy || "everyone";
            commentPrivacyInput.value = privacy.comment_privacy || "everyone";
            activityStatusInput.checked = Boolean(privacy.activity_status_visible);
            readReceiptsInput.checked = Boolean(privacy.read_receipts_enabled);
            tagApprovalInput.checked = Boolean(privacy.tagged_post_approval);
            followRequestsList.innerHTML = data.follow_requests?.length ? data.follow_requests.map((row) => createRequestItem(row.requester_username)).join("") : `<div class="panel-empty">No pending requests.</div>`;
            tagRequestsList.innerHTML = data.tag_requests?.length ? data.tag_requests.map((row) => createTagRequestItem(row)).join("") : `<div class="panel-empty">No pending tag requests.</div>`;
            blockedUsersList.innerHTML = data.blocked_users?.length ? data.blocked_users.map((name) => createPanelItem(escapeHtml(name), "Blocked account")).join("") : `<div class="panel-empty">No blocked users.</div>`;
            closeFriendsList.innerHTML = data.close_friends?.length ? data.close_friends.map((name) => createPanelItem(escapeHtml(name), "Close friend")).join("") : `<div class="panel-empty">No close friends yet.</div>`;
        } catch (err) {
            console.error("Failed to load privacy overview", err);
        }
    }

    function renderDbPost(postData) {
        const post = document.createElement("div");
        post.className = "post-main db-post";
        post.dataset.postId = String(postData.id);
        const captionText = (postData.caption_public ?? postData.caption ?? "").trim();
        const commentsHtml = (postData.comments || []).map(createCommentMarkup).join("");
        const postOwner = (postData.username || CURRENT_USER).trim();
        const isOwner = postOwner === CURRENT_USER;
        const avatar = postData.owner_profile?.avatar_url || "profile.jpeg";
        const headerAction = isOwner ? `<button class="deletePostBtn" data-owned="1" type="button">Delete</button>` : `<button class="post-action-btn followUserBtn" data-username="${escapeHtml(postOwner)}" type="button">${postData.viewer_follows_owner ? "Following" : "Follow"}</button>`;

        post.innerHTML = `
            <div class="post-header">
                <div class="post-left-header">
                    <div class="post-image"><img src="${escapeHtml(avatar)}" alt=""></div>
                    <p class="post-username">${escapeHtml(postOwner)}</p>
                    <i class="fa-solid fa-certificate"></i>
                    <span class="one-day"> . just now </span>
                </div>
                ${headerAction}
            </div>
            <div class="post-main-image">
                <img src="${API_BASE}${postData.image_url}" alt="" data-protected-media="1" draggable="false">
                <div class="media-watermark-grid" aria-hidden="true"></div>
                <div class="watermark">${escapeHtml(postOwner)}</div>
            </div>
            <div class="post-fotter">
                <div class="post-fotter-left">
                    <i class="fa-${postData.liked_by_user ? "solid" : "regular"} fa-heart likeBtn" data-liked="${postData.liked_by_user ? "1" : "0"}" style="${postData.liked_by_user ? "color:#ed4956;" : ""}"></i>
                    <i class="fa-regular fa-message"></i>
                    <i class="fa-regular fa-paper-plane"></i>
                </div>
                <i class="fa-${postData.saved_by_user ? "solid" : "regular"} fa-bookmark saveBtn" data-saved="${postData.saved_by_user ? "1" : "0"}"></i>
            </div>
            <div class="post-description">
                <p class="post-liked">${getLikeText(postData.likes_count || 0)}</p>
                <p class="savedMeta">Saved ${postData.saved_count || 0} times | ${escapeHtml(postData.visibility || "public")}</p>
                ${captionText ? `<p class="title"><span>${escapeHtml(postOwner)}</span> ${formatCaption(captionText)}</p>` : ""}
                ${renderRiskReport(postData.risk_report)}
                <div class="commentsList">${commentsHtml}</div>
                <input type="text" class="commentInput" placeholder="Add a comment...">
                <button class="commentBtn" type="button">Post</button>
                <p class="commentStatus"></p>
            </div>
        `;
        return post;
    }

    async function loadStoredPosts() {
        try {
            document.querySelectorAll(".db-post").forEach((node) => node.remove());
            const response = await fetch(`${API_BASE}/posts?username=${encodeURIComponent(CURRENT_USER)}&feed_mode=${encodeURIComponent(CURRENT_FEED_MODE)}`);
            if (!response.ok) return;
            const posts = await response.json();
            posts.reverse().forEach((postData) => feed.prepend(renderDbPost(postData)));
        } catch (err) {
            console.error("Failed to load posts", err);
        }
    }

    async function loadProfile() {
        try {
            const response = await fetch(`${API_BASE}/profile/${encodeURIComponent(CURRENT_USER)}?viewer=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            const profile = await response.json();
            sidebarUsername.innerText = profile.username;
            sidebarFullName.innerText = profile.full_name || profile.username;
            sidebarBio.innerText = profile.bio || "No bio yet.";
            postsCount.innerText = `${profile.posts.length || 0} posts`;
            followersCount.innerText = String(profile.followers_count || 0);
            followingCount.innerText = String(profile.following_count || 0);
            heroPostsCount.innerText = String(profile.posts.length || 0);
            heroFollowersCount.innerText = String(profile.followers_count || 0);
            heroFollowingCount.innerText = String(profile.following_count || 0);
            profileFullNameInput.value = profile.full_name || "";
            profileBioInput.value = profile.bio || "";
            profileAvatarInput.value = profile.avatar_url || "";
            privateAccountInput.checked = Boolean(profile.is_private);
            profileVisibilityInput.value = profile.privacy?.profile_visibility || "public";
            messagePrivacyInput.value = profile.privacy?.message_privacy || "everyone";
            commentPrivacyInput.value = profile.privacy?.comment_privacy || "everyone";
            activityStatusInput.checked = Boolean(profile.privacy?.activity_status_visible ?? true);
            readReceiptsInput.checked = Boolean(profile.privacy?.read_receipts_enabled ?? true);
            tagApprovalInput.checked = Boolean(profile.privacy?.tagged_post_approval ?? true);
            if (profile.avatar_url) {
                profileAvatarPreview.src = profile.avatar_url;
                navProfileAvatar.src = profile.avatar_url;
            }
        } catch (err) {
            console.error("Failed to load profile", err);
        }
    }

    async function loadNotifications() {
        try {
            const response = await fetch(`${API_BASE}/notifications?username=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            const data = await response.json();
            notificationList.innerHTML = data.length ? data.map((item) => createPanelItem(escapeHtml(item.message), item.is_read ? "Read" : "Unread", item.is_read ? "opacity:.65;" : "")).join("") : `<div class="panel-empty">No notifications yet.</div>`;
        } catch (err) {
            console.error("Failed to load notifications", err);
        }
    }

    async function loadSavedPosts() {
        try {
            const response = await fetch(`${API_BASE}/saved-posts?username=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            const data = await response.json();
            savedPostsList.innerHTML = data.length ? data.map((item) => createPanelItem(escapeHtml(item.username), escapeHtml(item.caption_public || item.caption || ""))).join("") : `<div class="panel-empty">No saved posts yet.</div>`;
        } catch (err) {
            console.error("Failed to load saved posts", err);
        }
    }

    async function loadModeration() {
        try {
            const response = await fetch(`${API_BASE}/moderation/logs?username=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            const data = await response.json();
            moderationList.innerHTML = data.slice(0, 8).map((row) => createPanelItem(`${escapeHtml(row.target_type)} | ${escapeHtml(row.status)}`, escapeHtml(row.reason || ""))).join("") || `<div class="panel-empty">No moderation activity.</div>`;
        } catch (err) {
            console.error("Failed to load moderation", err);
        }
    }

    async function loadStegoHistory() {
        try {
            const response = await fetch(`${API_BASE}/stego/history?username=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            const data = await response.json();
            stegoHistoryList.innerHTML = data.slice(0, 8).map((row) => createPanelItem(`${escapeHtml(row.filename)} | ${escapeHtml(row.verdict)}`, escapeHtml(row.reason || ""))).join("") || `<div class="panel-empty">No stego scan history.</div>`;
        } catch (err) {
            console.error("Failed to load stego history", err);
        }
    }

    async function loadMessages() {
        try {
            const peer = messagePeerInput.value.trim();
            if (!peer) {
                messageList.innerHTML = `<div class="panel-empty">Enter a username to load a conversation.</div>`;
                setStatus(messageStatus, "Enter a username to load messages.");
                return;
            }
            const response = await fetch(`${API_BASE}/messages?username=${encodeURIComponent(CURRENT_USER)}&peer=${encodeURIComponent(peer)}`);
            if (!response.ok) {
                let message = "Failed to load messages.";
                try {
                    const errorData = await response.json();
                    if (errorData.detail) message = errorData.detail;
                } catch (err) {}
                setStatus(messageStatus, message, "error");
                return;
            }
            const data = await response.json();
            messageList.innerHTML = data.slice(-10).map((row) => createPanelItem(escapeHtml(row.sender_username), `${escapeHtml(row.content)}${row.is_seen ? " • Seen" : ""}`)).join("") || `<div class="panel-empty">No messages in this conversation yet.</div>`;
            const readForm = new FormData();
            readForm.append("username", CURRENT_USER);
            readForm.append("peer", peer);
            fetch(`${API_BASE}/messages/read`, { method: "POST", body: readForm }).catch(() => {});
            setStatus(messageStatus, data.length ? `Showing the latest ${Math.min(data.length, 10)} message${data.length === 1 ? "" : "s"}.` : "No messages in this conversation yet.", data.length ? "success" : "");
        } catch (err) {
            console.error("Failed to load messages", err);
            setStatus(messageStatus, "Failed to load messages.", "error");
        }
    }

    function openComposer() {
        uploadModal.style.display = "block";
        setStatus(composerStatus, "Add an image to enable publishing.");
    }

    async function handleUpload() {
        if (!imageInput.files.length) {
            setStatus(composerStatus, "Select an image first.", "error");
            return;
        }
        const file = imageInput.files[0];
        if (!isSupportedImage(file)) {
            setStatus(composerStatus, "Unsupported image type. Use PNG, JPG, JPEG, BMP, TIFF, or WEBP.", "error");
            imageInput.value = "";
            previewImage.style.display = "none";
            return;
        }

        uploadBtn.disabled = true;
        setStatus(composerStatus, "Publishing post...");
        const formData = new FormData();
        formData.append("file", file);
        formData.append("hide", hideToggle.checked);
        formData.append("stego_strict", stegoStrictToggle && stegoStrictToggle.checked ? "1" : "0");
        formData.append("caption", captionInput.value);
        formData.append("username", CURRENT_USER);
        formData.append("visibility", visibilityInput.value);
        formData.append("blur_regions", manualBlurInput.value.trim());

        try {
            const response = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
            if (!response.ok) {
                let errorMessage = "Upload failed.";
                try {
                    const errorData = await response.json();
                    if (errorData.detail) errorMessage = errorData.detail;
                } catch (e) {}
                setStatus(composerStatus, errorMessage, "error");
                return;
            }

            const postData = await response.json();
            feed.prepend(renderDbPost(postData));
            uploadModal.style.display = "none";
            imageInput.value = "";
            captionInput.value = "";
            manualBlurInput.value = "";
            previewImage.style.display = "none";
            setStatus(composerStatus, "Post published.", "success");
            await loadProfile();
            await loadModeration();
            await loadStegoHistory();
        } catch (err) {
            console.error("Failed to upload post", err);
            const message = String(err?.message || "").includes("Failed to fetch")
                ? `Cannot reach ${API_BASE}. Start the backend server and try again.`
                : "Failed to publish post.";
            setStatus(composerStatus, message, "error");
        } finally {
            uploadBtn.disabled = false;
        }
    }

    openUpload.onclick = openComposer;
    heroCreateBtn.onclick = openComposer;
    closeModal.onclick = () => uploadModal.style.display = "none";
    uploadModal.onclick = (event) => { if (event.target === uploadModal) uploadModal.style.display = "none"; };

    imageInput.onchange = () => {
        const file = imageInput.files[0];
        if (!file) return;
        if (!isSupportedImage(file)) {
            setStatus(composerStatus, "Unsupported image type. Use PNG, JPG, JPEG, BMP, TIFF, or WEBP.", "error");
            imageInput.value = "";
            previewImage.style.display = "none";
            return;
        }
        previewImage.src = URL.createObjectURL(file);
        previewImage.style.display = "block";
        setStatus(composerStatus, `${file.name} is ready to publish.`, "success");
    };

    uploadBtn.onclick = handleUpload;
    createBtn.onclick = () => {
        if (!imageInput.files.length) {
            setStatus(composerStatus, "Choose an image to preview first.", "error");
            return;
        }
        setStatus(composerStatus, "Preview looks good. You can publish now.", "success");
    };

    searchBtn.onclick = async () => {
        const q = searchInput.value.trim();
        if (!q) {
            setStatus(searchStatus, "Type something to search.");
            searchResults.innerHTML = `<div class="panel-empty">Search results will appear here.</div>`;
            return;
        }
        try {
            setStatus(searchStatus, "Searching...");
            const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}&username=${encodeURIComponent(CURRENT_USER)}`);
            if (!response.ok) return;
            renderSearchResults(await response.json());
        } catch (err) {
            console.error("Failed to search", err);
            setStatus(searchStatus, "Search failed.", "error");
        }
    };

    markNotificationsReadBtn.onclick = async () => {
        const formData = new FormData();
        formData.append("username", CURRENT_USER);
        try {
            await fetch(`${API_BASE}/notifications/read-all`, { method: "POST", body: formData });
            await loadNotifications();
        } catch (err) {
            console.error("Failed to mark notifications read", err);
        }
    };

    loadSavedBtn.onclick = loadSavedPosts;
    saveProfileBtn.onclick = async () => {
        const formData = new FormData();
        formData.append("username", CURRENT_USER);
        formData.append("full_name", profileFullNameInput.value);
        formData.append("bio", profileBioInput.value);
        formData.append("avatar_url", profileAvatarInput.value);
        formData.append("is_private", privateAccountInput.checked ? "1" : "0");
        formData.append("profile_visibility", profileVisibilityInput.value);
        formData.append("message_privacy", messagePrivacyInput.value);
        formData.append("comment_privacy", commentPrivacyInput.value);
        formData.append("activity_status_visible", activityStatusInput.checked ? "1" : "0");
        formData.append("read_receipts_enabled", readReceiptsInput.checked ? "1" : "0");
        formData.append("tagged_post_approval", tagApprovalInput.checked ? "1" : "0");
        try {
            const response = await fetch(`${API_BASE}/profile/update`, { method: "POST", body: formData });
            if (response.ok) {
                await loadProfile();
                await loadPrivacyOverview();
                await loadStoredPosts();
                setStatus(profileStatus, "Profile updated.", "success");
            }
        } catch (err) {
            console.error("Failed to save profile", err);
            setStatus(profileStatus, "Failed to save profile.", "error");
        }
    };

    sendMessageBtn.onclick = async () => {
        const peer = messagePeerInput.value.trim();
        const content = messageInput.value.trim();
        if (!peer || !content) {
            setStatus(messageStatus, "Add both a recipient and a message.", "error");
            return;
        }
        const formData = new FormData();
        formData.append("sender_username", CURRENT_USER);
        formData.append("receiver_username", peer);
        formData.append("content", content);
        try {
            const response = await fetch(`${API_BASE}/messages`, { method: "POST", body: formData });
            if (response.ok) {
                messageInput.value = "";
                await loadMessages();
                await loadNotifications();
                setStatus(messageStatus, "Message sent.", "success");
            } else {
                let message = "Failed to send message.";
                try {
                    const errorData = await response.json();
                    if (errorData.detail) message = errorData.detail;
                } catch (err) {}
                setStatus(messageStatus, message, "error");
            }
        } catch (err) {
            console.error("Failed to send message", err);
            setStatus(messageStatus, "Failed to send message.", "error");
        }
    };

    blockUserBtn.onclick = async () => {
        const target = privacyTargetInput.value.trim();
        if (!target) {
            setStatus(privacyRelationsStatus, "Enter a username to block or unblock.", "error");
            return;
        }
        const formData = new FormData();
        formData.append("username", CURRENT_USER);
        formData.append("target_username", target);
        try {
            const response = await fetch(`${API_BASE}/privacy/block`, { method: "POST", body: formData });
            if (!response.ok) throw new Error("Unable to update block list.");
            const data = await response.json();
            setStatus(privacyRelationsStatus, data.blocked ? `${target} is now blocked.` : `${target} was removed from your block list.`, "success");
            privacyTargetInput.value = "";
            await loadPrivacyOverview();
            await loadStoredPosts();
        } catch (err) {
            console.error("Failed to update block list", err);
            setStatus(privacyRelationsStatus, "Failed to update block list.", "error");
        }
    };

    closeFriendBtn.onclick = async () => {
        const target = privacyTargetInput.value.trim();
        if (!target) {
            setStatus(privacyRelationsStatus, "Enter a username to manage close friends.", "error");
            return;
        }
        const formData = new FormData();
        formData.append("username", CURRENT_USER);
        formData.append("target_username", target);
        try {
            const response = await fetch(`${API_BASE}/privacy/close-friends`, { method: "POST", body: formData });
            if (!response.ok) throw new Error("Unable to update close friends.");
            const data = await response.json();
            setStatus(privacyRelationsStatus, data.is_close_friend ? `${target} added to close friends.` : `${target} removed from close friends.`, "success");
            privacyTargetInput.value = "";
            await loadPrivacyOverview();
        } catch (err) {
            console.error("Failed to update close friends", err);
            setStatus(privacyRelationsStatus, "Failed to update close friends.", "error");
        }
    };

    allFeedBtn.onclick = async () => {
        CURRENT_FEED_MODE = "all";
        feedStatusLabel.innerText = "Showing community posts";
        allFeedBtn.classList.add("active");
        allFeedBtn.classList.remove("secondary");
        followingFeedBtn.classList.remove("active");
        followingFeedBtn.classList.add("secondary");
        await loadStoredPosts();
    };

    followingFeedBtn.onclick = async () => {
        CURRENT_FEED_MODE = "following";
        feedStatusLabel.innerText = "Showing people you follow";
        followingFeedBtn.classList.add("active");
        followingFeedBtn.classList.remove("secondary");
        allFeedBtn.classList.remove("active");
        allFeedBtn.classList.add("secondary");
        await loadStoredPosts();
    };

    messagePeerInput.onchange = loadMessages;
    messagePeerInput.onkeydown = (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            loadMessages();
        }
    };
    messageInput.onkeydown = (event) => {
        if (event.key === "Enter" && event.ctrlKey) {
            event.preventDefault();
            sendMessageBtn.click();
        }
    };
    searchInput.onkeydown = (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            searchBtn.click();
        }
    };
    darkModeToggle.onclick = () => document.body.classList.toggle("dark-mode");

    document.addEventListener("click", async (e) => {
        if (e.target.classList.contains("likeBtn")) {
            const postContainer = e.target.closest(".post-main");
            const postId = postContainer?.dataset?.postId;
            if (!postId) {
                updateLikeButton(e.target, e.target.dataset.liked !== "1");
                return;
            }
            const likeForm = new FormData();
            likeForm.append("username", CURRENT_USER);
            try {
                const likeResponse = await fetch(`${API_BASE}/posts/${postId}/like`, { method: "POST", body: likeForm });
                if (!likeResponse.ok) return;
                const likeData = await likeResponse.json();
                updateLikeButton(e.target, likeData.liked);
                const likesLabel = postContainer.querySelector(".post-liked");
                if (likesLabel) likesLabel.innerText = getLikeText(likeData.likes_count || 0);
            } catch (err) {
                console.error("Failed to like post", err);
            }
            return;
        }

        if (e.target.classList.contains("saveBtn")) {
            const postContainer = e.target.closest(".post-main");
            const postId = postContainer?.dataset?.postId;
            if (!postId) {
                updateSaveButton(e.target, e.target.dataset.saved !== "1");
                return;
            }
            const saveForm = new FormData();
            saveForm.append("username", CURRENT_USER);
            try {
                const saveResponse = await fetch(`${API_BASE}/posts/${postId}/save`, { method: "POST", body: saveForm });
                if (!saveResponse.ok) return;
                const saveData = await saveResponse.json();
                updateSaveButton(e.target, saveData.saved);
                const desc = postContainer.querySelector(".savedMeta");
                if (desc) {
                    const visibility = (desc.innerText.split("|")[1] || "public").trim();
                    desc.innerText = `Saved ${saveData.saved_count || 0} times | ${visibility}`;
                }
                await loadSavedPosts();
            } catch (err) {
                console.error("Failed to save post", err);
            }
            return;
        }

        if (e.target.classList.contains("followUserBtn")) {
            const targetUser = e.target.dataset.username;
            if (!targetUser) return;
            const followForm = new FormData();
            followForm.append("follower_username", CURRENT_USER);
            followForm.append("following_username", targetUser);
            try {
                const followResponse = await fetch(`${API_BASE}/follow`, { method: "POST", body: followForm });
                if (!followResponse.ok) return;
                const followData = await followResponse.json();
                e.target.innerText = followData.is_following ? "Following" : (followData.request_status === "pending" ? "Requested" : "Follow");
                await loadProfile();
                await loadPrivacyOverview();
                await loadStoredPosts();
            } catch (err) {
                console.error("Failed to follow user", err);
            }
            return;
        }

        if (e.target.classList.contains("followRequestActionBtn")) {
            const requester = e.target.dataset.username;
            const action = e.target.dataset.action;
            if (!requester || !action) return;
            const formData = new FormData();
            formData.append("username", CURRENT_USER);
            formData.append("requester_username", requester);
            formData.append("action", action);
            try {
                const response = await fetch(`${API_BASE}/follow-requests/respond`, { method: "POST", body: formData });
                if (!response.ok) return;
                await loadPrivacyOverview();
                await loadProfile();
                await loadNotifications();
                setStatus(privacyRelationsStatus, `${requester} ${action === "approve" ? "approved" : "rejected"}.`, "success");
            } catch (err) {
                console.error("Failed to respond to follow request", err);
                setStatus(privacyRelationsStatus, "Failed to respond to the follow request.", "error");
            }
            return;
        }

        if (e.target.classList.contains("tagRequestActionBtn")) {
            const postId = e.target.dataset.postId;
            const action = e.target.dataset.action;
            if (!postId || !action) return;
            const formData = new FormData();
            formData.append("username", CURRENT_USER);
            formData.append("post_id", postId);
            formData.append("action", action);
            try {
                const response = await fetch(`${API_BASE}/tags/respond`, { method: "POST", body: formData });
                if (!response.ok) return;
                await loadPrivacyOverview();
                await loadNotifications();
                await loadStoredPosts();
                setStatus(privacyRelationsStatus, `Tag ${action === "approve" ? "approved" : "hidden"}.`, "success");
            } catch (err) {
                console.error("Failed to respond to tag request", err);
                setStatus(privacyRelationsStatus, "Failed to respond to tag request.", "error");
            }
            return;
        }

        if (e.target.classList.contains("tagLink")) {
            e.preventDefault();
            searchInput.value = `#${e.target.dataset.tag || ""}`;
            searchBtn.click();
            return;
        }

        if (e.target.classList.contains("mentionLink")) {
            e.preventDefault();
            searchInput.value = `@${e.target.dataset.user || ""}`;
            searchBtn.click();
            return;
        }

        if (e.target.classList.contains("deletePostBtn")) {
            if (e.target.dataset.owned !== "1") {
                alert("You can delete only your own posts.");
                return;
            }
            const postContainer = e.target.closest(".post-main");
            const postId = postContainer?.dataset?.postId;
            if (!postId) return;
            if (!window.confirm("Delete this post permanently?")) return;
            try {
                const deleteResponse = await fetch(`${API_BASE}/posts/${postId}?username=${encodeURIComponent(CURRENT_USER)}`, { method: "DELETE" });
                if (!deleteResponse.ok) {
                    let errorMessage = "Failed to delete post.";
                    try {
                        const errorData = await deleteResponse.json();
                        if (errorData.detail) errorMessage = errorData.detail;
                    } catch (err) {}
                    alert(errorMessage);
                    return;
                }
                postContainer.remove();
                await loadProfile();
            } catch (err) {
                console.error("Failed to delete post", err);
            }
            return;
        }

        if (!e.target.classList.contains("commentBtn")) return;

        const description = e.target.closest(".post-description");
        const input = description?.querySelector(".commentInput");
        const status = description?.querySelector(".commentStatus");
        const postContainer = e.target.closest(".post-main");
        const postId = postContainer?.dataset?.postId;
        const commentsList = postContainer?.querySelector(".commentsList");
        const comment = input?.value.trim();
        if (!comment || !input || !status) return;

        const formData = new FormData();
        formData.append("comment", comment);
        formData.append("username", CURRENT_USER);
        try {
            const moderationRes = await fetch(`${API_BASE}/check_comment`, { method: "POST", body: formData });
            const moderationData = await moderationRes.json();
            if (moderationData.status === "blocked") {
                status.style.color = "red";
                status.innerText = "Comment blocked (toxic)";
                return;
            }
            status.style.color = "green";
            status.innerText = `Allowed (${moderationData.sentiment})`;
            if (postId) {
                const saveFormData = new FormData();
                saveFormData.append("comment", comment);
                saveFormData.append("username", CURRENT_USER);
                const saveResponse = await fetch(`${API_BASE}/posts/${postId}/comments`, { method: "POST", body: saveFormData });
                if (!saveResponse.ok) {
                    let errorMessage = "Failed to save comment.";
                    try {
                        const errorData = await saveResponse.json();
                        if (errorData.detail) errorMessage = errorData.detail;
                    } catch (err) {}
                    status.style.color = "red";
                    status.innerText = errorMessage;
                    return;
                }
                const savedComment = await saveResponse.json();
                if (commentsList) {
                    const commentBox = document.createElement("p");
                    commentBox.innerHTML = `<strong>${escapeHtml(savedComment.username)}:</strong> ${escapeHtml(savedComment.content)}`;
                    commentsList.appendChild(commentBox);
                }
                await loadNotifications();
                await loadModeration();
            } else {
                const commentBox = document.createElement("p");
                commentBox.innerHTML = `<strong>${escapeHtml(CURRENT_USER)}:</strong> ${escapeHtml(comment)}`;
                commentsList?.appendChild(commentBox);
            }
            input.value = "";
        } catch (err) {
            console.error("Failed to comment", err);
            status.style.color = "red";
            status.innerText = "Failed to post comment.";
        }
    });

    loadStoredPosts();
    loadProfile();
    loadPrivacyOverview();
    loadNotifications();
    loadSavedPosts();
    loadModeration();
    loadStegoHistory();
    loadMessages();

    const privacyToast = document.createElement("div");
    privacyToast.className = "privacy-toast";
    privacyToast.setAttribute("role", "status");
    privacyToast.setAttribute("aria-live", "polite");
    document.body.appendChild(privacyToast);

    let privacyToastTimer;
    function showPrivacyToast(message) {
        privacyToast.textContent = message;
        privacyToast.classList.add("visible");
        window.clearTimeout(privacyToastTimer);
        privacyToastTimer = window.setTimeout(() => privacyToast.classList.remove("visible"), 2200);
    }

    document.addEventListener("dragstart", (event) => {
        if (event.target.closest("[data-protected-media='1']")) {
            event.preventDefault();
            showPrivacyToast("Protected media cannot be dragged from the page.");
        }
    });

    document.addEventListener("copy", (event) => {
        const selectedMedia = document.activeElement?.closest?.("[data-protected-media='1']");
        if (selectedMedia) {
            event.preventDefault();
            showPrivacyToast("Copy actions are limited for protected media.");
        }
    });
});



function showPrivacyToastFromGlobal(message) {
    const toast = document.querySelector(".privacy-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("visible");
    window.clearTimeout(window.__privacyToastTimer);
    window.__privacyToastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2200);
}

document.addEventListener("contextmenu", (e) => {
    if (e.target.closest("[data-protected-media='1']")) {
        e.preventDefault();
        showPrivacyToastFromGlobal("Right-click is disabled on protected media.");
        return;
    }
    e.preventDefault();
});
document.addEventListener("keydown", function(e) {
    if (e.key === "F12") e.preventDefault();
    if (e.ctrlKey && e.shiftKey && e.key === "I") e.preventDefault();
    if (e.ctrlKey && e.key.toLowerCase() === "u") e.preventDefault();
    if (e.key === "PrintScreen") {
        e.preventDefault();
        showPrivacyToastFromGlobal("Screenshot shortcuts were detected. This screen is marked as protected.");
    }
    if (e.ctrlKey && ["s", "p"].includes(e.key.toLowerCase())) {
        e.preventDefault();
        showPrivacyToastFromGlobal("Save and print shortcuts are blocked on this page.");
    }
});
window.addEventListener("blur", () => {
    const screenGuard = document.querySelector(".screen-guard");
    if (screenGuard) screenGuard.style.filter = "blur(20px)";
    showPrivacyToastFromGlobal("Protected media is active while the page is in the background.");
});
window.addEventListener("focus", () => {
    const screenGuard = document.querySelector(".screen-guard");
    if (screenGuard) screenGuard.style.filter = "none";
});
document.addEventListener("visibilitychange", function() {
    const screenGuard = document.querySelector(".screen-guard");
    if (screenGuard) screenGuard.style.filter = document.hidden ? "blur(10px)" : "none";
});
