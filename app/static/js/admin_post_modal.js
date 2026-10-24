// Modal xem nhanh chi tiết 1 bài đăng trong /admin/posts — gọi JSON (admin.post_detail),
// không reload trang. Nút Khóa/Xóa trong modal POST thẳng tới route đã có sẵn (full reload sau khi xong).
document.addEventListener("DOMContentLoaded", function () {
    var modalEl = document.getElementById("postDetailModal");
    if (!modalEl || typeof bootstrap === "undefined") return;
    var modal = new bootstrap.Modal(modalEl);

    function fillMedia(media) {
        var wrap = document.getElementById("pdm-media");
        wrap.innerHTML = "";
        if (!media || !media.length) {
            wrap.innerHTML = '<div class="text-secondary small">(Bài không có ảnh/video)</div>';
            return;
        }
        media.forEach(function (m) {
            var el;
            if (m.type === "video") {
                el = document.createElement("video");
                el.src = m.url;
                el.controls = true;
            } else {
                el = document.createElement("img");
                el.src = m.url;
                el.alt = "";
            }
            el.style.maxWidth = "100%";
            el.style.maxHeight = "300px";
            el.style.borderRadius = "8px";
            el.style.objectFit = "cover";
            el.className = "me-2 mb-2";
            wrap.appendChild(el);
        });
    }

    function setHideButton(isHidden) {
        var btn = document.querySelector("#pdm-form-hide button");
        if (isHidden) {
            btn.className = "btn btn-outline-success";
            btn.innerHTML = '<i class="bi bi-unlock-fill"></i> Mở khóa';
        } else {
            btn.className = "btn btn-outline-warning";
            btn.innerHTML = '<i class="bi bi-lock-fill"></i> Khóa';
        }
    }

    function csrf() {
        var m = document.querySelector('meta[name="csrf-token"]');
        return m ? m.getAttribute("content") : "";
    }

    function renderComments(comments) {
        var wrap = document.getElementById("pdm-comments-list");
        var base = wrap.getAttribute("data-delete-base");
        wrap.innerHTML = "";
        if (!comments || !comments.length) {
            wrap.innerHTML = '<div class="text-secondary small">(Chưa có bình luận nào)</div>';
            return;
        }
        comments.forEach(function (c) {
            var row = document.createElement("div");
            row.className = "d-flex justify-content-between align-items-start mb-2 pb-2";
            row.style.borderBottom = "1px solid #334155";
            row.dataset.commentId = c.id;

            var left = document.createElement("div");
            left.style.minWidth = "0";
            var head = document.createElement("div");
            head.className = "small text-secondary";
            head.innerHTML = (c.is_reply ? '<span class="badge bg-secondary bg-opacity-50 me-1">trả lời</span>' : "") +
                '<strong style="color:#38bdf8;">' + c.author + "</strong> &middot; " + c.created_at;
            var body = document.createElement("div");
            body.style.whiteSpace = "pre-wrap";
            body.style.wordBreak = "break-word";
            body.textContent = c.content;
            left.appendChild(head);
            left.appendChild(body);

            var delBtn = document.createElement("button");
            delBtn.className = "btn btn-sm btn-outline-light flex-shrink-0 ms-2";
            delBtn.innerHTML = '<i class="bi bi-trash"></i>';
            delBtn.title = "Xóa bình luận này";
            delBtn.addEventListener("click", function () {
                if (!confirm("Xóa bình luận này?")) return;
                var delUrl = base.replace("/0/", "/" + c.id + "/");
                fetch(delUrl, {
                    method: "POST",
                    headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() },
                })
                    .then(function (r) { return r.json(); })
                    .then(function (res) {
                        (res.deleted_ids || [c.id]).forEach(function (id) {
                            var node = wrap.querySelector('[data-comment-id="' + id + '"]');
                            if (node) node.remove();
                        });
                        var countEl = document.getElementById("pdm-comment-count");
                        var n = parseInt(countEl.textContent, 10) || 0;
                        countEl.textContent = Math.max(0, n - (res.deleted_count || 1));
                        if (!wrap.children.length) {
                            wrap.innerHTML = '<div class="text-secondary small">(Chưa có bình luận nào)</div>';
                        }
                    })
                    .catch(function () {
                        alert("Không xóa được bình luận.");
                    });
            });

            row.appendChild(left);
            row.appendChild(delBtn);
            wrap.appendChild(row);
        });
    }

    document.querySelectorAll(".adm-row-click").forEach(function (row) {
        row.addEventListener("click", function () {
            var url = row.getAttribute("data-detail-url");
            fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    document.getElementById("pdm-id").textContent = "#" + d.id;
                    document.getElementById("pdm-author").textContent = d.author;
                    document.getElementById("pdm-created").textContent = d.created_at;
                    document.getElementById("pdm-visibility").textContent = d.visibility;
                    document.getElementById("pdm-comment-count").textContent = d.comment_count;
                    document.getElementById("pdm-caption").textContent = d.caption || "(không có chữ)";
                    fillMedia(d.media);
                    renderComments(d.comments);
                    setHideButton(d.is_hidden);

                    var hideForm = document.getElementById("pdm-form-hide");
                    hideForm.action = hideForm.getAttribute("data-base").replace("/0/", "/" + d.id + "/");
                    var delForm = document.getElementById("pdm-form-delete");
                    delForm.action = delForm.getAttribute("data-base").replace("/0/", "/" + d.id + "/");

                    modal.show();
                })
                .catch(function () {
                    alert("Không tải được chi tiết bài đăng.");
                });
        });
    });
});
