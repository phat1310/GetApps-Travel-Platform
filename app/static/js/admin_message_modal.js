// Modal xem nội dung đầy đủ 1 hội thoại trong /admin/messages — chỉ gọi khi admin
// chủ động bấm vào 1 hội thoại cụ thể (route admin.conversation_detail), để hạn chế
// tải/đọc nội dung riêng tư ngoài nhu cầu kiểm duyệt thực tế.
document.addEventListener("DOMContentLoaded", function () {
    var modalEl = document.getElementById("convDetailModal");
    if (!modalEl || typeof bootstrap === "undefined") return;
    var modal = new bootstrap.Modal(modalEl);

    function esc(s) {
        var d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function renderMessages(d) {
        var wrap = document.getElementById("cdm-messages");
        wrap.innerHTML = "";
        if (!d.messages.length) {
            wrap.innerHTML = '<div class="text-secondary small text-center py-4">(Chưa có tin nhắn nào)</div>';
            return;
        }
        d.messages.forEach(function (m) {
            var row = document.createElement("div");
            row.className = "mb-3 pb-2";
            row.style.borderBottom = "1px solid #334155";

            var head = document.createElement("div");
            head.className = "small text-secondary mb-1";
            head.innerHTML = '<strong style="color:#38bdf8;">' + esc(m.sender) + "</strong> &middot; " + esc(m.created_at);
            row.appendChild(head);

            if (m.is_deleted) {
                var delNote = document.createElement("div");
                delNote.className = "fst-italic text-secondary small";
                delNote.textContent = "(tin nhắn đã bị thu hồi)";
                row.appendChild(delNote);
            } else {
                if (m.body) {
                    var body = document.createElement("div");
                    body.style.whiteSpace = "pre-wrap";
                    body.textContent = m.body;
                    row.appendChild(body);
                }
                if (m.file_url) {
                    if (m.file_kind === "image") {
                        var img = document.createElement("img");
                        img.src = m.file_url;
                        img.style.maxWidth = "220px";
                        img.style.maxHeight = "220px";
                        img.style.borderRadius = "8px";
                        img.className = "mt-1 d-block";
                        row.appendChild(img);
                    } else if (m.file_kind === "video") {
                        var vid = document.createElement("video");
                        vid.src = m.file_url;
                        vid.controls = true;
                        vid.style.maxWidth = "260px";
                        vid.className = "mt-1 d-block";
                        row.appendChild(vid);
                    } else {
                        var a = document.createElement("a");
                        a.href = m.file_url;
                        a.target = "_blank";
                        a.rel = "noopener";
                        a.className = "mt-1 d-inline-block";
                        a.innerHTML = '<i class="bi bi-paperclip"></i> ' + esc(m.file_name || "Tệp đính kèm");
                        row.appendChild(a);
                    }
                }
            }
            wrap.appendChild(row);
        });
        wrap.scrollTop = wrap.scrollHeight;
    }

    document.querySelectorAll(".adm-row-click").forEach(function (row) {
        row.addEventListener("click", function () {
            var url = row.getAttribute("data-detail-url");
            fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    document.getElementById("cdm-id").textContent = "#" + d.id;
                    document.getElementById("cdm-pair").textContent = d.user_a + " ↔ " + d.user_b;
                    renderMessages(d);
                    modal.show();
                })
                .catch(function () {
                    alert("Không tải được nội dung hội thoại.");
                });
        });
    });
});
