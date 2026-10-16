/* GesPlace — ô chọn ĐỊA ĐIỂM theo danh mục hành chính (tỉnh/thành → phường/xã/đặc khu).
 * Dùng: <input data-place-picker data-place-code-name="location_code"> (tự gắn khi trang tải)
 *       hoặc GesPlace.attach(input, {codeName:'location_code'}).
 * - Gõ chữ: hiện gợi ý (gõ đúng tên → 1 dòng; gõ gần đúng → nhiều dòng). Gõ kèm tỉnh ("Quán Gió, Đà Lạt") → xếp vào tỉnh đó.
 * - Bấm vào ô: mở bảng chọn: chọn Tỉnh/Thành trước, rồi mới hiện Phường/Xã của tỉnh đó, bấm OK để điền.
 * - Kết quả: ô hiện nhãn "Thành phố Hồ Chí Minh, Phường Bến Thành" (lớn → nhỏ) + input ẩn chứa MÃ địa điểm gửi lên server.
 * Chỗ cụ thể (quán, homestay…) để liên kết Google Maps lo. Mọi chuỗi từ server chỉ đưa vào bằng textContent. */
(function () {
  'use strict';
  if (window.GesPlace) return;
  var BASE = '/locations/places';
  var provCache = null, wardCache = {};
  var pop = null, curInput = null, mode = '', pending = null, timer = null, seq = 0;

  function norm(s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().replace(/[^a-z0-9]/g, '');
  }
  function mk(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function getJSON(url) {
    return fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } }).then(function (r) { return r.json(); });
  }
  function provinces() {
    if (provCache) return Promise.resolve(provCache);
    return getJSON(BASE + '/provinces').then(function (d) { provCache = d.provinces || []; return provCache; });
  }
  function wards(code) {
    if (wardCache[code]) return Promise.resolve(wardCache[code]);
    return getJSON(BASE + '/wards?province=' + encodeURIComponent(code)).then(function (d) { wardCache[code] = d.wards || []; return wardCache[code]; });
  }

  /* ---------- trạng thái của từng ô ---------- */
  function st(input) { return input._gp; }
  function setValue(input, label, code, pcode) {
    var s = st(input); s.label = label || ''; s.code = code || ''; s.pcode = pcode || (code && String(code).length <= 3 ? code : '');
    input.value = s.label; s.hidden.value = s.code;
    input.classList.remove('is-invalid');
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function attach(input, opts) {
    if (!input || input._gp) return input && input._gp;
    opts = opts || {};
    var hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = opts.codeName || input.getAttribute('data-place-code-name') || 'location_code';
    input.insertAdjacentElement('afterend', hidden);
    input.setAttribute('autocomplete', 'off');
    input._gp = { hidden: hidden, code: '', label: '', pcode: '' };
    input.addEventListener('input', function () {
      var s = st(input);
      if (input.value !== s.label) { s.code = ''; s.hidden.value = ''; }
      clearTimeout(timer);
      var q = input.value.trim();
      if (!q) { openBrowse(input, true); return; }
      timer = setTimeout(function () { openSuggest(input, q); }, 160);
    });
    input.addEventListener('focus', function () { if (!input.value.trim()) openBrowse(input); });
    input.addEventListener('click', function () { if (!pop || curInput !== input) { if (!input.value.trim() || st(input).code) openBrowse(input); } });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
      if (e.key === 'Enter' && mode === 'suggest' && pop) {
        var first = pop.querySelector('.gp-item'); if (first) { e.preventDefault(); first.click(); }
      }
    });
    input.addEventListener('blur', function () {            // gõ đúng tên rồi rời ô → tự nhận nếu chỉ có đúng 1 kết quả
      var q = input.value.trim(), s = st(input);
      if (!q || s.code) return;
      setTimeout(function () {
        if (st(input).code || input.value.trim() !== q) return;
        getJSON(BASE + '/suggest?limit=3&q=' + encodeURIComponent(q)).then(function (d) {
          var r = d.results || [];
          if (r.length === 1 && (norm(r[0].name) === norm(q) || norm(r[0].label) === norm(q))) { if (st(input).code === '') setValue(input, r[0].label, r[0].code, r[0].kind === 'ward' ? r[0].province_code : r[0].code); }
          else if (!st(input).code && !input.hasAttribute('data-place-lenient')) input.classList.add('is-invalid');
        }).catch(function () {});
      }, 180);
    });
    return input._gp;
  }

  /* ---------- khung nổi dùng chung ---------- */
  function host(input) { return input.closest('.modal') || document.body; }   // trong modal Bootstrap phải nằm trong modal để gõ được
  function ensurePop(input, cls) {
    close();
    pop = mk('div', 'gp-pop ' + cls);
    pop.setAttribute('role', 'dialog');
    pop.addEventListener('mousedown', function (e) { if (!/INPUT|TEXTAREA/.test(e.target.tagName)) e.preventDefault(); });
    host(input).appendChild(pop);
    curInput = input;
    place();
    return pop;
  }
  function place() {
    if (!pop || !curInput) return;
    var r = curInput.getBoundingClientRect(), vw = window.innerWidth, vh = window.innerHeight;
    if (vw <= 576) { pop.style.cssText = ''; pop.classList.add('gp-sheet'); return; }
    pop.classList.remove('gp-sheet');
    var w = Math.min(pop.classList.contains('gp-browse') ? 580 : Math.max(r.width, 340), vw - 16);
    var left = Math.max(8, Math.min(r.left, vw - w - 8));
    var below = vh - r.bottom - 12, above = r.top - 12;
    var maxh = Math.max(220, Math.min(460, below >= 280 || below >= above ? below : above));
    pop.style.width = w + 'px'; pop.style.left = left + 'px'; pop.style.maxHeight = maxh + 'px';
    if (below >= 280 || below >= above) { pop.style.top = (r.bottom + 4) + 'px'; pop.style.bottom = 'auto'; }
    else { pop.style.bottom = (vh - r.top + 4) + 'px'; pop.style.top = 'auto'; }
  }
  function close() {
    if (pop && pop.parentNode) pop.parentNode.removeChild(pop);
    pop = null; curInput = null; mode = ''; pending = null;
    var b = document.querySelector('.gp-backdrop'); if (b) b.remove();
  }
  document.addEventListener('mousedown', function (e) {
    if (pop && !pop.contains(e.target) && e.target !== curInput) close();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && pop) close(); });
  window.addEventListener('resize', place);
  window.addEventListener('scroll', place, true);

  /* ---------- gợi ý khi gõ ---------- */
  function row(item, onPick) {
    var b = mk('button', 'gp-item'); b.type = 'button';
    b.appendChild(mk('span', 'gp-ico', item.kind === 'province' ? '🏙️' : '📍'));
    var t = mk('span', 'gp-txt');
    t.appendChild(mk('span', 'gp-main', item.label));
    if (item.note) t.appendChild(mk('span', 'gp-note', item.note));
    b.appendChild(t);
    b.addEventListener('click', function () { onPick(item); });
    return b;
  }
  function openSuggest(input, q) {
    var my = ++seq;
    getJSON(BASE + '/suggest?q=' + encodeURIComponent(q) + (pending && pending.prov ? '&province=' + pending.prov.code : '')).then(function (d) {
      if (my !== seq || input.value.trim() !== q) return;
      var p = (mode === 'suggest' && curInput === input && pop) ? pop : ensurePop(input, 'gp-suggest');
      mode = 'suggest'; p.textContent = '';
      var res = d.results || [];
      if (!res.length) p.appendChild(mk('div', 'gp-empty', 'Không tìm thấy. Thử gõ tên tỉnh/thành hoặc phường/xã gần đúng.'));
      res.forEach(function (it) { p.appendChild(row(it, function (x) { setValue(input, x.label, x.code, x.kind === 'ward' ? x.province_code : x.code); close(); })); });
      var more = mk('button', 'gp-more', 'Duyệt theo tỉnh/thành…'); more.type = 'button';
      more.addEventListener('click', function () { openBrowse(input); });
      p.appendChild(more);
      place();
    }).catch(function () { });
  }

  /* ---------- bảng chọn Tỉnh → Phường/Xã ---------- */
  function openBrowse(input, noFocus) {
    var s = st(input), p = ensurePop(input, 'gp-browse');
    mode = 'browse'; pending = { prov: null, ward: null };
    var head = mk('div', 'gp-head');
    head.appendChild(mk('strong', '', 'Chọn địa điểm'));
    var x = mk('button', 'gp-x', '✕'); x.type = 'button'; x.setAttribute('aria-label', 'Đóng'); x.addEventListener('click', close);
    head.appendChild(x); p.appendChild(head);
    var search = mk('input', 'gp-search'); search.type = 'search'; search.placeholder = 'Tìm nhanh: gõ tên tỉnh, phường, xã…'; search.autocomplete = 'off';
    p.appendChild(search);
    var cols = mk('div', 'gp-cols');
    var cP = mk('div', 'gp-col'), cW = mk('div', 'gp-col');
    cP.appendChild(mk('div', 'gp-coltitle', '① Tỉnh / Thành phố'));
    cW.appendChild(mk('div', 'gp-coltitle', '② Phường / Xã / Đặc khu'));
    var lP = mk('div', 'gp-list'), lW = mk('div', 'gp-list');
    cP.appendChild(lP); cW.appendChild(lW); cols.appendChild(cP); cols.appendChild(cW);
    var results = mk('div', 'gp-list gp-results'); results.style.display = 'none';
    p.appendChild(cols); p.appendChild(results);
    var sum = mk('div', 'gp-sum');
    var foot = mk('div', 'gp-foot');
    var clr = mk('button', 'gp-btn gp-clear', 'Xóa lựa chọn'); clr.type = 'button';
    var ok = mk('button', 'gp-btn gp-ok', 'OK'); ok.type = 'button'; ok.disabled = true;
    foot.appendChild(sum); foot.appendChild(clr); foot.appendChild(ok); p.appendChild(foot);

    function label() { return pending.ward ? pending.ward.label : (pending.prov ? pending.prov.label : ''); }
    function refreshSum() {
      if (!pending) return;
      sum.textContent = label() || 'Chưa chọn — hãy chọn Tỉnh/Thành trước';
      ok.disabled = !pending.prov;
    }
    function mark(list, code) {
      Array.prototype.forEach.call(list.children, function (b) { b.classList.toggle('active', b.dataset.code === code); });
    }
    function drawProv(list) {
      lP.textContent = '';
      list.forEach(function (pv) {
        var b = mk('button', 'gp-opt', pv.full); b.type = 'button'; b.dataset.code = pv.code;
        b.addEventListener('click', function () { pending.prov = pv; pending.ward = null; mark(lP, pv.code); loadWards(pv.code); refreshSum(); });
        lP.appendChild(b);
      });
    }
    function loadWards(code, keepWard) {
      lW.textContent = ''; lW.appendChild(mk('div', 'gp-empty', 'Đang tải…'));
      wards(code).then(function (ws) {
        if (!pending || !pending.prov || pending.prov.code !== code) return;
        lW.textContent = '';
        ws.forEach(function (w) {
          var b = mk('button', 'gp-opt', w.full); b.type = 'button'; b.dataset.code = w.code;
          b.addEventListener('click', function () { pending.ward = w; mark(lW, w.code); refreshSum(); });
          lW.appendChild(b);
        });
        if (keepWard) { mark(lW, keepWard); var a = lW.querySelector('.active'); if (a) a.scrollIntoView({ block: 'nearest' }); }
      }).catch(function () { lW.textContent = ''; lW.appendChild(mk('div', 'gp-empty', 'Không tải được danh sách.')); });
    }
    lW.appendChild(mk('div', 'gp-empty', 'Hãy chọn Tỉnh/Thành phố ở cột bên trái trước.'));
    provinces().then(function (list) {
      if (!pop || !pop.contains(lP)) return;               // bảng đã đóng trong lúc chờ tải
      drawProv(list);
      var cur = st(input).code, pc = st(input).pcode;
      var pv = pc && list.filter(function (x) { return x.code === pc; })[0];
      if (cur && pv) {                                     // mở lại đúng chỗ đã chọn
        pending.prov = pv; mark(lP, pv.code); loadWards(pv.code, cur !== pv.code ? cur : null);
        if (cur !== pv.code) pending.ward = { code: cur, label: s.label };
        refreshSum();
        var a0 = lP.querySelector('.active'); if (a0) a0.scrollIntoView({ block: 'nearest' });
      }
    }).catch(function () { lP.appendChild(mk('div', 'gp-empty', 'Không tải được danh sách.')); });
    refreshSum();

    var qTimer = null, qSeq = 0;
    search.addEventListener('input', function () {
      clearTimeout(qTimer);
      var q = search.value.trim();
      if (!q) { results.style.display = 'none'; cols.style.display = ''; return; }
      qTimer = setTimeout(function () {
        if (!pending || !pop || !pop.contains(search)) return;
        var my = ++qSeq;
        getJSON(BASE + '/suggest?limit=20&q=' + encodeURIComponent(q) + (pending.prov ? '&province=' + pending.prov.code : '')).then(function (d) {
          if (my !== qSeq || !pending) return;
          cols.style.display = 'none'; results.style.display = ''; results.textContent = '';
          var res = d.results || [];
          if (!res.length) results.appendChild(mk('div', 'gp-empty', 'Không tìm thấy kết quả phù hợp.'));
          res.forEach(function (it) {
            results.appendChild(row(it, function (x) {
              provinces().then(function (list) {
                var pcode = x.kind === 'province' ? x.code : x.province_code;
                var pv = list.filter(function (z) { return z.code === pcode; })[0];
                if (!pv) return;
                pending.prov = pv; pending.ward = x.kind === 'ward' ? x : null;
                search.value = ''; results.style.display = 'none'; cols.style.display = '';
                mark(lP, pv.code); loadWards(pv.code, x.kind === 'ward' ? x.code : null); refreshSum();
                var a = lP.querySelector('.active'); if (a) a.scrollIntoView({ block: 'nearest' });
              });
            }));
          });
        }).catch(function () { });
      }, 160);
    });
    clr.addEventListener('click', function () { setValue(input, '', ''); close(); input.focus(); });
    ok.addEventListener('click', function () {
      if (!pending.prov) return;
      setValue(input, label(), pending.ward ? pending.ward.code : pending.prov.code, pending.prov.code);
      close();
    });
    place();
    if (!noFocus) setTimeout(function () { if (pop && pop.contains(search)) search.focus(); }, 30);
  }

  /* ---------- cảnh báo link Google Maps lệch tỉnh (chỉ gợi ý, người dùng vẫn đăng được) ---------- */
  function csrf() { var m = document.querySelector('meta[name="csrf-token"]'); return m ? m.getAttribute('content') : ''; }
  // opts: {kind:'post'|'plan', locations:[{name,code}], links:[{url,label}]}  →  Promise<true = cứ đăng | false = quay lại sửa>
  function guard(opts) {
    var links = (opts.links || []).filter(function (l) { return l && l.url; });
    var locs = (opts.locations || []).filter(function (l) { return l && (l.name || l.code); });
    if (!links.length || !locs.length) return Promise.resolve(true);
    return fetch(BASE + '/check-links', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), 'Accept': 'application/json' },
      body: JSON.stringify({ kind: opts.kind || 'post', locations: locs, links: links })
    }).then(function (r) { return r.ok ? r.json() : {}; }).then(function (d) {
      if (!d || !d.warning) return true;
      if (typeof window.geAsk === 'function') {
        return window.geAsk({ title: 'Link bản đồ có vẻ lệch địa điểm', note: d.warning, fields: [], confirmText: 'Vẫn đăng', cancelText: 'Sửa lại' }).then(function (ok) { return !!ok; });
      }
      return window.confirm(d.warning + '\n\nBấm OK để vẫn đăng.');
    }).catch(function () { return true; });          // lỗi mạng khi kiểm tra: không chặn người dùng
  }

  window.GesPlace = {
    guard: guard,
    attach: attach,
    init: function (root) {
      Array.prototype.forEach.call((root || document).querySelectorAll('input[data-place-picker]'), function (i) { attach(i); });
    },
    set: function (input, label, code) { if (!input._gp) attach(input); setValue(input, label, code); },
    code: function (input) { return input && input._gp ? input._gp.code : ''; },
    reset: function (input) { if (input && input._gp) { input._gp.code = ''; input._gp.label = ''; input._gp.hidden.value = ''; input.value = ''; input.classList.remove('is-invalid'); } }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { window.GesPlace.init(); });
  else window.GesPlace.init();
})();
