/*
 * GesCrop — hộp thoại căn chỉnh ảnh trước khi lưu (kéo để di chuyển, phóng to / thu nhỏ, xem đúng khung sẽ hiển thị).
 * Dùng cho: ảnh đại diện (khung tròn 1:1), ảnh nền trang cá nhân (2:1), ảnh bìa lịch trình (16:9).
 *
 *   GesCrop.open({file | url, aspect, outW, round, title, guides, minW, minH, allowReplace, state, fileName}) -> Promise<{file, blob, state, original} | null>
 *   GesCrop.attach(input, opts)   // chặn sự kiện 'change' của <input type=file>, mở hộp thoại, rồi thay file đã chọn bằng ảnh đã cắt
 *   GesCrop.readjust(input)       // mở lại hộp thoại với ảnh gốc đã chọn trước đó (nhớ vị trí / mức phóng to)
 *
 * Toàn bộ xử lý ở trình duyệt (canvas). Server vẫn kiểm tra lại file như mọi lần tải lên khác.
 */
(function () {
    "use strict";
    if (window.GesCrop) return;

    var CSS = [
        ".gesc-overlay{position:fixed;inset:0;z-index:2100;background:rgba(2,6,23,.62);display:none;align-items:center;justify-content:center;padding:16px;-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px)}",
        ".gesc-overlay.show{display:flex}",
        ".gesc-box{width:min(560px,100%);max-height:100%;overflow:auto;background:#fff;color:#0f172a;border-radius:20px;box-shadow:0 24px 70px rgba(0,0,0,.4);display:flex;flex-direction:column;font-family:inherit}",
        "[data-bs-theme=dark] .gesc-box{background:#1e293b;color:#f1f5f9}",
        ".gesc-head{display:flex;align-items:center;gap:10px;padding:14px 18px}",
        ".gesc-title{flex:1;font-weight:800;font-size:1.05rem}",
        ".gesc-x{width:34px;height:34px;border-radius:50%;border:0;background:rgba(100,116,139,.16);color:inherit;font-size:1.1rem;line-height:1;cursor:pointer}",
        ".gesc-x:hover{background:rgba(100,116,139,.3)}",
        ".gesc-stage{position:relative;height:340px;margin:0 18px;border-radius:14px;overflow:hidden;background:#0b1220;touch-action:none;cursor:grab;user-select:none;-webkit-user-select:none}",
        ".gesc-stage.drag{cursor:grabbing}",
        ".gesc-img{position:absolute;left:0;top:0;max-width:none;max-height:none;transform-origin:0 0;pointer-events:none;user-select:none;will-change:transform}",
        ".gesc-frame{position:absolute;box-sizing:border-box;border:2px solid #fff;box-shadow:0 0 0 9999px rgba(2,6,23,.6);pointer-events:none;"
            + "background-image:linear-gradient(to right,transparent calc(33.33% - .5px),rgba(255,255,255,.28) 33.33%,transparent calc(33.33% + .5px),transparent calc(66.66% - .5px),rgba(255,255,255,.28) 66.66%,transparent calc(66.66% + .5px)),"
            + "linear-gradient(to bottom,transparent calc(33.33% - .5px),rgba(255,255,255,.28) 33.33%,transparent calc(33.33% + .5px),transparent calc(66.66% - .5px),rgba(255,255,255,.28) 66.66%,transparent calc(66.66% + .5px))}",
        ".gesc-frame.round{border-radius:50%;background-image:none}",
        ".gesc-guide{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);border-top:2px dashed #fbbf24;border-bottom:2px dashed #fbbf24;box-sizing:border-box}",
        ".gesc-vguide{position:absolute;top:0;bottom:0;left:50%;transform:translateX(-50%);border-left:2px dotted #ef4444;border-right:2px dotted #ef4444;box-sizing:border-box;pointer-events:none}",
        ".gesc-vguide span{position:absolute;left:50%;bottom:6px;transform:translateX(-50%);background:rgba(127,29,29,.85);color:#fecaca;font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap}",
        ".gesc-guide span{position:absolute;left:8px;top:4px;background:rgba(15,23,42,.78);color:#fde68a;font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap}",
        ".gesc-zoom{display:flex;align-items:center;gap:10px;padding:14px 18px 4px}",
        ".gesc-zbtn{width:34px;height:34px;border-radius:50%;border:1px solid rgba(100,116,139,.4);background:transparent;color:inherit;font-size:1.2rem;line-height:1;cursor:pointer;flex:none}",
        ".gesc-zbtn:hover{background:rgba(100,116,139,.18)}",
        ".gesc-range{flex:1;accent-color:#0ea5e9;height:28px;cursor:pointer}",
        ".gesc-hint{padding:0 18px;font-size:.74rem;color:#64748b}",
        "[data-bs-theme=dark] .gesc-hint{color:#94a3b8}",
        ".gesc-err{margin:10px 18px 0;padding:8px 12px;border-radius:10px;background:#fee2e2;color:#991b1b;font-size:.84rem;display:none}",
        "[data-bs-theme=dark] .gesc-err{background:#450a0a;color:#fecaca}",
        ".gesc-foot{display:flex;align-items:center;gap:8px;padding:14px 18px 16px}",
        ".gesc-foot .sp{flex:1}",
        ".gesc-btn{border:0;border-radius:12px;padding:.6rem 1.2rem;font-weight:700;font-size:.9rem;cursor:pointer}",
        ".gesc-btn.ghost{background:transparent;color:#0284c7;padding-left:.4rem;padding-right:.4rem}",
        ".gesc-btn.ghost:hover{text-decoration:underline}",
        ".gesc-btn.cancel{background:rgba(100,116,139,.18);color:inherit}",
        ".gesc-btn.ok{background:#0ea5e9;color:#fff}",
        ".gesc-btn.ok:hover{background:#0284c7}",
        ".gesc-btn:disabled{opacity:.5;cursor:not-allowed}",
        ".gesc-btn:focus-visible,.gesc-x:focus-visible,.gesc-zbtn:focus-visible{outline:3px solid rgba(14,165,233,.55);outline-offset:2px}",
        "@media (max-width:575.98px){.gesc-stage{height:300px}.gesc-box{border-radius:16px}}"
    ].join("\n");

    var dom = null, cur = null;

    function h(tag, cls, text) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text != null) e.textContent = text;
        return e;
    }

    function build() {
        if (dom) return dom;
        var st = document.createElement("style");
        st.textContent = CSS;
        document.head.appendChild(st);

        var overlay = h("div", "gesc-overlay");
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        var box = h("div", "gesc-box");
        var head = h("div", "gesc-head");
        var title = h("div", "gesc-title", "Căn chỉnh ảnh");
        title.id = "gescTitle";
        overlay.setAttribute("aria-labelledby", "gescTitle");
        var x = h("button", "gesc-x", "✕");
        x.type = "button"; x.setAttribute("aria-label", "Đóng");
        head.appendChild(title); head.appendChild(x);

        var stage = h("div", "gesc-stage");
        var img = h("img", "gesc-img"); img.alt = ""; img.draggable = false;
        var frame = h("div", "gesc-frame");
        stage.appendChild(img); stage.appendChild(frame);

        var err = h("div", "gesc-err"); err.setAttribute("role", "alert");

        var zoom = h("div", "gesc-zoom");
        var zm = h("button", "gesc-zbtn", "−"); zm.type = "button"; zm.setAttribute("aria-label", "Thu nhỏ");
        var range = h("input", "gesc-range"); range.type = "range"; range.min = "1"; range.max = "4"; range.step = "0.01"; range.value = "1";
        range.setAttribute("aria-label", "Phóng to / thu nhỏ");
        var zp = h("button", "gesc-zbtn", "+"); zp.type = "button"; zp.setAttribute("aria-label", "Phóng to");
        zoom.appendChild(zm); zoom.appendChild(range); zoom.appendChild(zp);
        var hint = h("div", "gesc-hint", "Kéo ảnh để di chuyển · Cuộn chuột, kéo thanh trượt hoặc chụm hai ngón để phóng to / thu nhỏ.");

        var foot = h("div", "gesc-foot");
        var rep = h("button", "gesc-btn ghost", "Chọn ảnh khác"); rep.type = "button";
        var cancel = h("button", "gesc-btn cancel", "Hủy"); cancel.type = "button";
        var ok = h("button", "gesc-btn ok", "Dùng ảnh này"); ok.type = "button";
        foot.appendChild(rep); foot.appendChild(h("span", "sp")); foot.appendChild(cancel); foot.appendChild(ok);

        var file = document.createElement("input");
        file.type = "file"; file.accept = "image/jpeg,image/png,image/webp,image/gif"; file.hidden = true;

        box.appendChild(head); box.appendChild(stage); box.appendChild(err); box.appendChild(zoom); box.appendChild(hint); box.appendChild(foot); box.appendChild(file);
        overlay.appendChild(box);
        document.body.appendChild(overlay);

        dom = {overlay: overlay, box: box, title: title, x: x, stage: stage, img: img, frame: frame, err: err, range: range, zm: zm, zp: zp,
               rep: rep, cancel: cancel, ok: ok, file: file, hint: hint};
        wire();
        return dom;
    }

    // ------------------------------------------------------------------ hình học
    function layout() {
        var s = cur; if (!s) return;
        var sw = dom.stage.clientWidth, sh = dom.stage.clientHeight, pad = 18;
        s.sw = sw; s.sh = sh;
        if (s.opts.round) { s.fw = s.fh = Math.max(40, Math.min(sw, sh) - pad * 2); }
        else { s.fw = Math.max(40, Math.min(sw - pad * 2, (sh - pad * 2) * s.aspect)); s.fh = s.fw / s.aspect; }
        var f = dom.frame;
        f.style.width = s.fw + "px"; f.style.height = s.fh + "px";
        f.style.left = ((sw - s.fw) / 2) + "px"; f.style.top = ((sh - s.fh) / 2) + "px";
        f.classList.toggle("round", !!s.opts.round);
        if (s.img) {
            s.minS = Math.max(s.fw / s.nw, s.fh / s.nh);
            s.cx = s.nx * s.fw; s.cy = s.ny * s.fh;
        }
        render();
    }

    function clamp() {
        var s = cur, dw = s.nw * s.minS * s.z, dh = s.nh * s.minS * s.z;
        var mx = Math.max(0, (dw - s.fw) / 2), my = Math.max(0, (dh - s.fh) / 2);
        s.cx = Math.min(mx, Math.max(-mx, s.cx));
        s.cy = Math.min(my, Math.max(-my, s.cy));
    }

    function render() {
        var s = cur; if (!s || !s.img) return;
        clamp();
        var sc = s.minS * s.z, dw = s.nw * sc, dh = s.nh * sc;
        s.nx = s.cx / s.fw; s.ny = s.cy / s.fh;
        dom.img.style.width = dw + "px"; dom.img.style.height = dh + "px";
        dom.img.style.transform = "translate(" + (s.sw / 2 + s.cx - dw / 2) + "px," + (s.sh / 2 + s.cy - dh / 2) + "px)";
        dom.range.value = String(s.z);
    }

    function setZoom(z) {
        var s = cur; if (!s || !s.img) return;
        z = Math.min(4, Math.max(1, z));
        var r = z / s.z; s.cx *= r; s.cy *= r; s.z = z;       // giữ nguyên điểm ảnh đang nằm giữa khung
        render();
    }

    // ------------------------------------------------------------------ nạp ảnh
    function showError(msg) {
        dom.err.textContent = msg || ""; dom.err.style.display = msg ? "block" : "none";
    }

    function loadSource(blobOrUrl) {
        var s = cur;
        showError("");
        dom.ok.disabled = true;
        s.img = false;
        dom.img.removeAttribute("src");
        dom.img.style.width = dom.img.style.height = "0px";
        var url, isBlob = typeof blobOrUrl !== "string";
        if (isBlob) { url = URL.createObjectURL(blobOrUrl); s.urls.push(url); } else { url = blobOrUrl; }
        var probe = new Image();
        try {
            if (!isBlob && new URL(url, location.href).origin !== location.origin) probe.crossOrigin = "anonymous";
        } catch (e) { /* url lạ: để trình duyệt tự xử lý */ }
        probe.onload = function () {
            if (cur !== s) return;
            var nw = probe.naturalWidth, nh = probe.naturalHeight;
            if (!nw || !nh) { showError("Không đọc được ảnh này. Hãy chọn một file ảnh JPG, PNG hoặc WebP hợp lệ."); return; }
            if ((s.opts.minW && nw < s.opts.minW) || (s.opts.minH && nh < s.opts.minH)) {
                showError("Ảnh quá nhỏ (" + nw + "×" + nh + "px). Cần tối thiểu " + (s.opts.minW || 0) + "×" + (s.opts.minH || 0) + "px để không bị vỡ khi phủ kín khung.");
                return;
            }
            s.imgEl = probe; s.nw = nw; s.nh = nh; s.img = true;
            dom.img.src = url;
            s.z = 1; s.nx = 0; s.ny = 0;
            if (s.restore && s.restore.z) { s.z = s.restore.z; s.nx = s.restore.nx || 0; s.ny = s.restore.ny || 0; s.restore = null; }
            dom.ok.disabled = false;
            layout();
            dom.ok.focus();
        };
        probe.onerror = function () {
            if (cur !== s) return;
            showError(isBlob ? "Không đọc được ảnh này. Hãy chọn một file ảnh JPG, PNG hoặc WebP hợp lệ."
                             : "Không thể căn chỉnh ảnh từ nguồn ngoài. Hãy chọn ảnh từ thiết bị của bạn.");
        };
        probe.src = url;
    }

    // ------------------------------------------------------------------ kết thúc
    function finish(result) {
        var s = cur; if (!s) return;
        cur = null;
        dom.overlay.classList.remove("show");
        document.body.style.overflow = s.prevOverflow || "";
        s.urls.forEach(function (u) { try { URL.revokeObjectURL(u); } catch (e) { /* bỏ qua */ } });
        dom.img.removeAttribute("src");
        document.removeEventListener("keydown", onKey, true);
        window.removeEventListener("resize", layout);
        if (s.lastFocus && s.lastFocus.focus) { try { s.lastFocus.focus(); } catch (e) { /* bỏ qua */ } }
        s.resolve(result);
    }

    function confirm() {
        var s = cur; if (!s || !s.img) return;
        var outW = s.opts.outW || 1600, outH = Math.round(outW / s.aspect);
        var sc = s.minS * s.z;
        var cxImg = s.nw / 2 - s.cx / sc, cyImg = s.nh / 2 - s.cy / sc;       // điểm ảnh đang nằm giữa khung
        var sw = s.fw / sc, sh = s.fh / sc;
        var sx = Math.min(Math.max(0, cxImg - sw / 2), s.nw - sw), sy = Math.min(Math.max(0, cyImg - sh / 2), s.nh - sh);
        var cv = document.createElement("canvas");
        cv.width = outW; cv.height = outH;
        var ctx = cv.getContext("2d");
        ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, outW, outH);          // ảnh PNG trong suốt -> nền trắng
        ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
        try {
            ctx.drawImage(s.imgEl, sx, sy, sw, sh, 0, 0, outW, outH);
        } catch (e) { showError("Không xử lý được ảnh này."); return; }
        dom.ok.disabled = true;
        var state = {z: s.z, nx: s.nx, ny: s.ny};
        try {
            cv.toBlob(function (blob) {
                if (!blob) { dom.ok.disabled = false; showError("Không thể xuất ảnh (ảnh từ nguồn ngoài không cho phép chỉnh sửa). Hãy chọn ảnh từ thiết bị."); return; }
                var name = (s.opts.fileName || "image") .replace(/\.[a-z0-9]+$/i, "") + ".jpg";
                var f;
                try { f = new File([blob], name, {type: "image/jpeg", lastModified: Date.now()}); } catch (e) { f = blob; f.name = name; }
                finish({file: f, blob: blob, state: state, original: s.original || null});
            }, "image/jpeg", 0.92);
        } catch (e) {
            dom.ok.disabled = false;
            showError("Không thể xuất ảnh (ảnh từ nguồn ngoài không cho phép chỉnh sửa). Hãy chọn ảnh từ thiết bị.");
        }
    }

    // ------------------------------------------------------------------ sự kiện
    function onKey(e) {
        if (!cur) return;
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(null); return; }
        if (e.key === "Tab") {                                              // giữ focus trong hộp thoại
            var f = Array.prototype.filter.call(dom.box.querySelectorAll("button,input[type=range]"), function (n) { return !n.disabled && n.offsetParent !== null; });
            if (!f.length) return;
            var first = f[0], last = f[f.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
            else if (!dom.box.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
            return;
        }
        var t = document.activeElement, tag = t ? t.tagName : "";
        if (e.key === "Enter") { if (tag !== "BUTTON") { e.preventDefault(); confirm(); } return; }
        if (!cur.img) return;
        if (tag === "INPUT" && e.key.indexOf("Arrow") === 0) return;         // thanh trượt tự xử lý phím mũi tên
        var step = e.shiftKey ? 30 : 10, used = true;
        if (e.key === "ArrowLeft") cur.cx += step;
        else if (e.key === "ArrowRight") cur.cx -= step;
        else if (e.key === "ArrowUp") cur.cy += step;
        else if (e.key === "ArrowDown") cur.cy -= step;
        else if (e.key === "+" || e.key === "=") setZoom(cur.z + 0.15);
        else if (e.key === "-" || e.key === "_") setZoom(cur.z - 0.15);
        else used = false;
        if (used) { e.preventDefault(); render(); }
    }

    function wire() {
        var d = dom, ptrs = {}, pinch = null;
        d.x.addEventListener("click", function () { finish(null); });
        d.cancel.addEventListener("click", function () { finish(null); });
        d.ok.addEventListener("click", confirm);
        d.overlay.addEventListener("mousedown", function (e) { if (e.target === d.overlay) finish(null); });
        d.zm.addEventListener("click", function () { setZoom(cur.z - 0.2); });
        d.zp.addEventListener("click", function () { setZoom(cur.z + 0.2); });
        d.range.addEventListener("input", function () { setZoom(parseFloat(d.range.value)); });
        d.rep.addEventListener("click", function () { d.file.value = ""; d.file.click(); });
        d.file.addEventListener("change", function () {
            var f = d.file.files && d.file.files[0];
            if (!f || !cur) return;
            cur.original = f; cur.restore = null; cur.opts.fileName = f.name;
            loadSource(f);
        });
        d.stage.addEventListener("wheel", function (e) {
            if (!cur || !cur.img) return;
            e.preventDefault();
            setZoom(cur.z * Math.exp(-e.deltaY * 0.0015));
        }, {passive: false});
        d.stage.addEventListener("pointerdown", function (e) {
            if (!cur || !cur.img) return;
            try { d.stage.setPointerCapture(e.pointerId); } catch (x) { /* bỏ qua */ }
            ptrs[e.pointerId] = {x: e.clientX, y: e.clientY};
            d.stage.classList.add("drag");
            var ids = Object.keys(ptrs);
            if (ids.length === 2) {
                var a = ptrs[ids[0]], b = ptrs[ids[1]];
                pinch = {dist: Math.hypot(a.x - b.x, a.y - b.y) || 1, z: cur.z};
            }
        });
        d.stage.addEventListener("pointermove", function (e) {
            var p = ptrs[e.pointerId]; if (!p || !cur) return;
            var ids = Object.keys(ptrs);
            if (ids.length === 1) {
                cur.cx += e.clientX - p.x; cur.cy += e.clientY - p.y;
                p.x = e.clientX; p.y = e.clientY;
                render();
            } else if (ids.length === 2 && pinch) {
                p.x = e.clientX; p.y = e.clientY;
                var a = ptrs[ids[0]], b = ptrs[ids[1]];
                setZoom(pinch.z * (Math.hypot(a.x - b.x, a.y - b.y) / pinch.dist));
            }
        });
        function up(e) {
            delete ptrs[e.pointerId];
            if (Object.keys(ptrs).length < 2) pinch = null;
            if (!Object.keys(ptrs).length) d.stage.classList.remove("drag");
        }
        d.stage.addEventListener("pointerup", up);
        d.stage.addEventListener("pointercancel", up);
    }

    // ------------------------------------------------------------------ API
    function open(opts) {
        opts = opts || {};
        if (cur) finish(null);
        build();
        return new Promise(function (resolve) {
            var aspect = opts.round ? 1 : (opts.aspect || 1);
            cur = {opts: opts, aspect: aspect, resolve: resolve, urls: [], img: false, z: 1, nx: 0, ny: 0, cx: 0, cy: 0,
                   original: opts.file || null, restore: opts.state || null,
                   lastFocus: document.activeElement, prevOverflow: document.body.style.overflow};
            dom.title.textContent = opts.title || "Căn chỉnh ảnh";
            dom.rep.style.display = opts.allowReplace === false ? "none" : "";
            dom.frame.innerHTML = "";
            (opts.guides || []).forEach(function (g) {                       // dải gạch đứt: vùng sẽ hiện ở một khung khác
                if (!g || !g.ratio || g.ratio === aspect) return;
                if (g.ratio < aspect) {                                       // khung hẹp hơn ảnh cắt: hiện 2 đường chấm đỏ dọc (vùng giữa là phần được hiển thị)
                    var vg = h("div", "gesc-vguide"); vg.style.width = (g.ratio / aspect * 100) + "%";
                    vg.appendChild(h("span", "", g.label || ""));
                    dom.frame.appendChild(vg);
                    return;
                }
                var gd = h("div", "gesc-guide"); gd.style.height = (aspect / g.ratio * 100) + "%";
                gd.appendChild(h("span", "", g.label || ""));
                dom.frame.appendChild(gd);
            });
            document.body.style.overflow = "hidden";
            dom.overlay.classList.add("show");
            document.addEventListener("keydown", onKey, true);
            window.addEventListener("resize", layout);
            layout();
            if (opts.file) loadSource(opts.file);
            else if (opts.url) loadSource(opts.url);
            else { dom.ok.disabled = true; dom.rep.focus(); }
        });
    }

    function setFiles(input, file) {
        var dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
    }

    function fire(input) {
        var ev = new Event("change", {bubbles: true});
        ev.gesCropped = true;
        input.dispatchEvent(ev);
    }

    function attach(input, opts) {
        if (!input || input._gesAttached) return;
        input._gesAttached = true;
        input._gesOpts = opts || {};
        input.addEventListener("change", function (e) {
            if (e.gesCropped) return;                                       // sự kiện do chính mình phát lại sau khi cắt
            var f = input.files && input.files[0];
            if (!f) return;
            e.stopImmediatePropagation();
            var o = Object.assign({}, input._gesOpts, {file: f, fileName: f.name});
            open(o).then(function (res) {
                if (!res) { input.value = ""; return; }
                input._gesCrop = {original: res.original || f, state: res.state};
                setFiles(input, res.file);
                fire(input);
            });
        }, true);
    }

    function readjust(input) {
        var c = input && input._gesCrop;
        if (!c) return Promise.resolve(null);
        var o = Object.assign({}, input._gesOpts, {file: c.original, fileName: c.original.name || "image", state: c.state});
        return open(o).then(function (res) {
            if (!res) return null;
            input._gesCrop = {original: res.original || c.original, state: res.state};
            setFiles(input, res.file);
            fire(input);
            return res;
        });
    }

    window.GesCrop = {open: open, attach: attach, readjust: readjust};
})();
