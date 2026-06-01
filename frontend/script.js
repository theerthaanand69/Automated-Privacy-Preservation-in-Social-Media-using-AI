const API_BASE = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
    const openUpload = document.getElementById("openUpload");
    const uploadModal = document.getElementById("uploadModal");
    const closeModal = document.getElementById("closeModal");
    const createBtn = document.getElementById("createBtn");
    const uploadBtn = document.getElementById("uploadBtn");
    const imageInput = document.getElementById("imageInput");
    const hideToggle = document.getElementById("hideToggle");
    const captionInput = document.getElementById("captionInput");
    const feed = document.getElementById("feed");
    const currentUser = (localStorage.getItem("username") || "user").trim() || "user";

    if (openUpload && uploadModal) {
        openUpload.addEventListener("click", () => {
            uploadModal.style.display = "block";
        });
    }

    if (closeModal && uploadModal) {
        closeModal.addEventListener("click", () => {
            uploadModal.style.display = "none";
        });
    }

    if (createBtn && imageInput) {
        createBtn.addEventListener("click", () => {
            if (!imageInput.files.length) {
                alert("Please select an image first");
                return;
            }
            alert("Image selected. Click Upload to post.");
        });
    }

    if (uploadBtn && imageInput && hideToggle && feed) {
        uploadBtn.addEventListener("click", async () => {
            if (!imageInput.files.length) {
                alert("Select an image first");
                return;
            }

            const formData = new FormData();
            formData.append("file", imageInput.files[0]);
            formData.append("hide", String(hideToggle.checked));
            formData.append("caption", captionInput ? captionInput.value : "");
            formData.append("username", currentUser);

            const response = await fetch(`${API_BASE}/upload`, {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                alert(err.detail || "Upload failed.");
                return;
            }

            const postData = await response.json();
            const post = document.createElement("div");
            post.className = "post-main";
            post.dataset.postId = String(postData.id || "");
            post.innerHTML = `
                <div class="post-main-image">
                    <img src="${API_BASE}${postData.image_url}" style="width:100%;" alt="">
                    <div class="watermark">${postData.username || currentUser}</div>
                </div>
                <div class="post-description">
                    <div class="commentsList"></div>
                    <input type="text" class="commentInput" placeholder="Add a comment...">
                    <button class="commentBtn">Post</button>
                    <p class="commentStatus"></p>
                </div>
            `;
            feed.prepend(post);

            if (uploadModal) uploadModal.style.display = "none";
            imageInput.value = "";
            if (captionInput) captionInput.value = "";
        });
    }

    document.addEventListener("click", async (e) => {
        if (!e.target.classList.contains("commentBtn")) return;

        const post = e.target.closest(".post-description");
        if (!post) return;

        const input = post.querySelector(".commentInput");
        const status = post.querySelector(".commentStatus");
        const commentsList = post.querySelector(".commentsList");
        const postContainer = e.target.closest(".post-main");
        const postId = postContainer ? postContainer.dataset.postId : null;
        if (!input || !status || !commentsList) return;

        const comment = input.value.trim();
        if (!comment) return;

        const moderationForm = new FormData();
        moderationForm.append("comment", comment);

        const moderationRes = await fetch(`${API_BASE}/check_comment`, {
            method: "POST",
            body: moderationForm
        });
        const moderationData = await moderationRes.json();

        if (moderationData.status === "blocked") {
            status.style.color = "red";
            status.innerText = "Comment blocked (toxic)";
            return;
        }

        if (!postId) {
            status.style.color = "green";
            status.innerText = `Allowed (${moderationData.sentiment})`;
            const commentDiv = document.createElement("p");
            commentDiv.innerHTML = `<strong>${currentUser}</strong> ${comment}`;
            commentsList.appendChild(commentDiv);
            input.value = "";
            return;
        }

        const saveForm = new FormData();
        saveForm.append("comment", comment);
        saveForm.append("username", currentUser);

        const saveRes = await fetch(`${API_BASE}/posts/${postId}/comments`, {
            method: "POST",
            body: saveForm
        });

        if (!saveRes.ok) {
            const err = await saveRes.json().catch(() => ({}));
            status.style.color = "red";
            status.innerText = err.detail || "Failed to save comment.";
            return;
        }

        const saved = await saveRes.json();
        status.style.color = "green";
        status.innerText = `Allowed (${saved.sentiment})`;
        const commentDiv = document.createElement("p");
        commentDiv.innerHTML = `<strong>${saved.username}</strong> ${saved.content}`;
        commentsList.appendChild(commentDiv);
        input.value = "";
    });
});
