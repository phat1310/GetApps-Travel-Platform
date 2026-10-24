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
                    document.getElementById("idm-description").textContent = d.description || "(không có mô tả)";

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
