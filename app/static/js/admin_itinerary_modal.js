// Modal xem nhanh chi tiết 1 lịch trình trong /admin/itineraries — gọi JSON (admin.itinerary_detail),
// không reload trang. Nút Khóa/Xóa trong modal POST thẳng tới route đã có sẵn (full reload sau khi xong).
document.addEventListener("DOMContentLoaded", function () {
    var modalEl = document.getElementById("itineraryDetailModal");
    if (!modalEl || typeof bootstrap === "undefined") return;
    var modal = new bootstrap.Modal(modalEl);

    function setHideButton(isHidden) {
        var btn = document.querySelector("#idm-form-hide button");
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
        var wrap = document.getElementById("idm-comments-list");
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
            // content_html đã được server escape + biến URL thành link <a> (xem linkify_comment
            // trong app/admin/routes.py) — an toàn để gán thẳng innerHTML.
            body.innerHTML = c.content_html || "";
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
                        var countEl = document.getElementById("idm-comment-count");
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
                    document.getElementById("idm-id").textContent = "#" + d.id;
                    document.getElementById("idm-author").textContent = d.author;
                    document.getElementById("idm-created").textContent = d.created_at;
                    document.getElementById("idm-visibility").textContent = d.visibility;
                    document.getElementById("idm-comment-count").textContent = d.comment_count;
                    document.getElementById("idm-days").textContent = d.total_days;
                    document.getElementById("idm-title").textContent = d.title || "(không có tiêu đề)";
                    document.getElementById("idm-destination").textContent = d.destination || "—";
                    var descEl = document.getElementById("idm-description");
                    descEl.innerHTML = d.description_html || "";
                    if (!d.description) descEl.textContent = "(không có mô tả)";

                    var coverWrap = document.getElementById("idm-cover");
                    coverWrap.innerHTML = "";
                    if (d.cover_url) {
                        var img = document.createElement("img");
                        img.src = d.cover_url;
                        img.style.maxWidth = "100%";
                        img.style.maxHeight = "280px";
                        img.style.borderRadius = "8px";
                        img.style.objectFit = "cover";
                        coverWrap.appendChild(img);
                    }

                    var attachWrap = document.getElementById("idm-attachment");
                    attachWrap.innerHTML = "";
                    if (d.attachment_url) {
                        var a = document.createElement("a");
                        a.href = d.attachment_url;
                        a.target = "_blank";
                        a.rel = "noopener noreferrer nofollow";
                        a.className = "text-info";
                        a.innerHTML = '<i class="bi bi-paperclip"></i> ' + (d.attachment_name || "Tệp đính kèm");
                        attachWrap.appendChild(a);
                    }

                    renderComments(d.comments);
                    setHideButton(d.is_hidden);

                    var hideForm = document.getElementById("idm-form-hide");
                    hideForm.action = hideForm.getAttribute("data-base").replace("/0/", "/" + d.id + "/");
                    var delForm = document.getElementById("idm-form-delete");
                    delForm.action = delForm.getAttribute("data-base").replace("/0/", "/" + d.id + "/");

                    modal.show();
                })
                .catch(function () {
                    alert("Không tải được chi tiết lịch trình.");
                });
        });
    });
});
