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
