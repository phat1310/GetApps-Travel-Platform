/* GEs Around — nút radar + khung gợi ý quanh bạn.
 * - Mọi chuỗi từ server (tên địa điểm lấy từ OSM/Overture = dữ liệu KHÔNG tin cậy) chỉ được gắn bằng textContent.
 * - Tìm kiếm chạy nền: đóng khung vẫn chạy; chuyển trang thì tự chạy lại (kết quả/tiến trình lưu trong sessionStorage).
 * - Toạ độ GPS chỉ nằm trong bộ nhớ trang và gửi 1 lần lên server để tính; không lưu lâu dài.
 */
(function () {
  'use strict';
  var root = document.getElementById('gaRoot');
  if (!root) return;
  var $fab = document.getElementById('gaFab'), $panel = document.getElementById('gaPanel'),
      $body = document.getElementById('gaBody'), $badge = document.getElementById('gaBadge'),
      $tip = document.getElementById('gaTip'), $close = document.getElementById('gaClose');
  var KEY = 'gesAround.v1';
  var VEH_ICON = { walk: '🚶', bike: '🚲', motorbike: '🛵', car: '🚗', bus: '🚌' };
  var VEH_LABEL = { walk: 'Đi bộ', bike: 'Xe đạp', motorbike: 'Xe máy', car: 'Ô tô', bus: 'Xe buýt' };
  var GRP_ICON = { an_uong: ['🍜', 'f'], giai_tri: ['🎡', 'g'], tham_quan: ['🏛️', 't'] };
  var GRP_LABEL = { an_uong: 'Ăn uống', giai_tri: 'Giải trí', tham_quan: 'Tham quan địa danh' };
  var FREE = [[30, '30 phút'], [45, '45 phút'], [60, '1 giờ'], [90, '1,5 giờ'], [120, '2 giờ'], [180, '3 giờ'], [240, '4 giờ'], [360, '6 giờ'], [480, '8 giờ']];
  var BUDGETS = [[50000, '50k'], [100000, '100k'], [200000, '200k'], [500000, '500k'], [null, 'Không giới hạn']];
  var SVG_PIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>';
  var SVG_GPS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>';
  var SVG_RADAR = '<svg viewBox="0 0 120 120" aria-hidden="true"><defs><linearGradient id="gaG" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1789c3" stop-opacity="0"/><stop offset="1" stop-color="#1789c3" stop-opacity=".45"/></linearGradient></defs><circle cx="60" cy="60" r="54" fill="none" stroke="#bfe0f2" stroke-width="2"/><circle cx="60" cy="60" r="36" fill="none" stroke="#bfe0f2" stroke-width="2"/><circle cx="60" cy="60" r="18" fill="none" stroke="#bfe0f2" stroke-width="2"/><g class="ga-sweep"><path d="M60 60 L60 6 A54 54 0 0 1 106 34 Z" fill="url(#gaG)"/><path d="M60 60 L106 34" stroke="#1789c3" stroke-width="3" stroke-linecap="round"/></g><circle cx="60" cy="60" r="4" fill="#1789c3"/><circle cx="84" cy="44" r="4" fill="#17a673"/><circle cx="42" cy="76" r="4" fill="#f59e0b"/></svg>';

  var S = {
    open: false, view: 'form', meta: null, metaErr: null, pickOpen: false, pickQ: '', gpsBusy: false, error: '', result: null,
    form: { areaId: 'nguyen-hue', gps: null, free: 120, budget: null, unl: false, needs: { an_uong: true, giai_tri: false, tham_quan: true }, vehicle: 'motorbike' },
    running: false, seen: true, pending: null
  };

  /* ---------- tiện ích ---------- */
  function el(tag, props, kids) {
    var n = document.createElement(tag);
    if (props) for (var k in props) {
      if (k === 'text') n.textContent = props[k];
      else if (k === 'html') n.innerHTML = props[k];           // CHỈ dùng cho SVG hằng số trong file này
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), props[k]);
      else if (props[k] !== null && props[k] !== undefined && props[k] !== false) n.setAttribute(k, props[k] === true ? '' : props[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function csrf() { var m = document.querySelector('meta[name="csrf-token"]'); return m ? m.content : ''; }
  function save() {
    try {
      var p = { running: S.running, seen: S.seen, form: S.form, result: S.result, pending: S.running ? S.pending : null };
      if (!S.running && p.form.gps) p.form = Object.assign({}, p.form, { gps: null });   // không giữ toạ độ khi đã xong
      sessionStorage.setItem(KEY, JSON.stringify(p));
    } catch (e) {}
  }
  function load() {
    try {
      var p = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (!p) return;
      if (p.form && p.form.needs && p.form.free) S.form = p.form;
      S.result = p.result || null; S.seen = p.seen !== false; S.pending = p.pending || null; S.running = !!p.running;
    } catch (e) {}
  }
  function money(n) { return (Math.round(n / 100) / 10).toString().replace('.', ','); }
  function costText(c) {
    if (!c) return '';
    if (c.max === 0) return 'Miễn phí';
    var hi = c.max >= 1000 ? money(c.max) + 'k' : c.max + 'đ';
    if (c.min === 0) return 'Tối đa ~' + hi;
    return '~' + (c.min >= 1000 ? money(c.min) : c.min) + '–' + hi;
  }
  function fmtBudget(n) { return n === null || n === undefined ? '' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
  function freeLabel(m) { for (var i = 0; i < FREE.length; i++) if (FREE[i][0] === m) return FREE[i][1]; return m + ' phút'; }
  function areaName(id) {
    var a = (S.meta && S.meta.areas || []).filter(function (x) { return x.id === id; })[0];
    return a ? a.name : '';
  }

  /* ---------- mở / đóng ---------- */
  function setOpen(v) {
    S.open = v;
    $panel.hidden = !v;
    $fab.setAttribute('aria-expanded', v ? 'true' : 'false');
    if (v) {
      S.seen = true; save(); updateFab(); render(); ensureMeta();
    }
  }
  function updateFab() {
    $fab.classList.toggle('running', S.running);
    var news = !S.running && S.result && !S.seen && !S.open;
    $fab.classList.toggle('has-news', !!news || (S.running && !S.open));
    if (news) {
      var n = (S.result.vehicles[S.result.query.vehicle] || {}).total || 0;
      $badge.textContent = n > 99 ? '99+' : String(n); $badge.hidden = false;
      $tip.textContent = 'Có ' + n + ' gợi ý quanh bạn';
    } else {
      $badge.hidden = true;
      $tip.textContent = S.running && !S.open ? 'Đang tìm quanh bạn…' : 'GEs Around';
    }
  }

  /* ---------- dữ liệu khu vực ---------- */
  function ensureMeta() {
    if (S.meta || S.metaLoading) return;
    S.metaLoading = true;
    fetch(root.dataset.areasUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { if (!r.ok) throw new Error('http'); return r.json(); })
      .then(function (j) { S.meta = j; S.metaErr = null; })
      .catch(function () { S.metaErr = 'Không tải được danh sách khu vực. Hãy thử lại.'; })
      .then(function () { S.metaLoading = false; if (S.open) render(); });
  }

  /* ---------- gửi tìm kiếm ---------- */
  function buildQuery() {
    var f = S.form, needs = Object.keys(f.needs).filter(function (k) { return f.needs[k]; });
    var origin = f.gps ? { type: 'gps', lat: f.gps.lat, lng: f.gps.lng } : { type: 'area', id: f.areaId };
    return { free_minutes: f.free, needs: needs, budget: f.budget, vehicle: f.vehicle, origin: origin };
  }
  function validate() {
    var q = buildQuery();
    if (!q.needs.length) return 'Hãy chọn ít nhất một nhu cầu.';
    if (q.origin.type === 'area' && !q.origin.id) return 'Hãy chọn địa điểm hiện tại của bạn.';
    return '';
  }
  function runSearch(q) {
    S.running = true; S.pending = q; S.error = ''; S.view = 'loading'; S.seen = false;
    save(); updateFab(); render();
    fetch(root.dataset.searchUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(q)
    }).then(function (r) {
      var ct = r.headers.get('content-type') || '';
      if (ct.indexOf('json') < 0) throw { msg: 'Phiên đăng nhập có thể đã hết hạn. Hãy tải lại trang.' };
      return r.json().then(function (j) { if (!r.ok || !j.ok) throw { msg: j.error || 'Có lỗi xảy ra, thử lại nhé.' }; return j; });
    }).then(function (j) {
      S.result = j; S.error = ''; S.view = 'results';
      if (S.form.vehicle && j.vehicles[S.form.vehicle]) j.query.vehicle = S.form.vehicle;
    }).catch(function (e) {
      S.error = (e && e.msg) || 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'; S.view = 'form'; S.result = null;
    }).then(function () {
      if (S.unloading) return;                                // đang rời trang: giữ nguyên trạng thái 'running' để trang sau chạy lại
      S.running = false; S.pending = null; S.seen = S.open;
      S.form.gps = null;                                      // quên toạ độ ngay khi xong
      save(); updateFab(); render();
    });
  }

  /* ---------- vẽ giao diện ---------- */
  function render() {
    if (!S.open) return;
    $body.textContent = '';
    if (S.view === 'loading') return $body.appendChild(viewLoading());
    if (S.view === 'results' && S.result) return $body.appendChild(viewResults());
    $body.appendChild(viewForm());
  }

  function viewLoading() {
    var q = S.pending || buildQuery();
    var where = q.origin.type === 'gps' ? 'Vị trí của bạn' : areaName(q.origin.id) || 'TP.HCM';
    return el('div', null, [el('div', { class: 'ga-box ga-ld' }, [
      el('div', { html: SVG_RADAR }),
      el('h4', { text: 'Đang tìm quanh bạn…' }),
      el('p', { text: where + ' · ' + freeLabel(q.free_minutes) + ' · ' + (q.budget === null ? 'Không giới hạn' : fmtBudget(q.budget) + 'đ') + ' · ' + VEH_LABEL[q.vehicle] }),
      el('div', { class: 'ga-bgnote', text: '💡 Bạn có thể đóng cửa sổ này. GEs vẫn tìm ở nền, nút radar sẽ báo khi xong.' })
    ])]);
  }

  function viewForm() {
    var f = S.form, wrap = el('div');
    if (S.error) wrap.appendChild(el('div', { class: 'ga-err', role: 'alert', text: S.error }));
    var box1 = el('div', { class: 'ga-box' });
    box1.appendChild(el('span', { class: 'ga-lbl', text: 'Địa điểm hiện tại' }));
    var curName = f.gps ? 'Vị trí hiện tại của bạn' : (areaName(f.areaId) || 'Chọn khu vực / địa danh');
    var locBtn = el('button', { type: 'button', class: 'ga-loc', 'aria-haspopup': 'listbox', 'aria-expanded': S.pickOpen ? 'true' : 'false',
      onclick: function () { S.pickOpen = !S.pickOpen; S.pickQ = ''; render(); if (S.pickOpen) { var i = $body.querySelector('.ga-pick input'); if (i) i.focus(); } } }, [
      el('span', { html: SVG_PIN, style: 'display:flex' }),
      el('span', { class: 'ga-lock', text: 'TP.HCM 🔒' }),
      el('span', { class: 'ga-locname', text: curName }),
      el('span', { text: S.pickOpen ? '▴' : '▾' })
    ]);
    box1.appendChild(locBtn);
    if (S.pickOpen) box1.appendChild(viewPicker());
    var gps = el('button', { type: 'button', class: 'ga-gps', disabled: S.gpsBusy, onclick: useGps }, [el('span', { html: SVG_GPS, style: 'display:flex' }), S.gpsBusy ? 'Đang lấy vị trí…' : 'Dùng vị trí của tôi']);
    box1.appendChild(gps);
    box1.appendChild(el('div', { class: 'ga-hint', text: 'Hiện hỗ trợ TP.HCM mới (gồm Bình Dương, Bà Rịa – Vũng Tàu). Vị trí chỉ dùng để tính, không được lưu.' }));

    var sel = el('select', { id: 'gaFree', 'aria-label': 'Thời gian rảnh', onchange: function (e) { f.free = parseInt(e.target.value, 10); save(); } },
      FREE.map(function (o) { return el('option', { value: o[0], selected: o[0] === f.free }, [o[1]]); }));
    var inp = el('input', { id: 'gaBudget', type: 'text', inputmode: 'numeric', autocomplete: 'off', maxlength: '11', placeholder: 'Nhập số tiền', 'aria-label': 'Ngân sách (VNĐ)', value: fmtBudget(f.budget),
      oninput: function (e) { var d = e.target.value.replace(/\D/g, '').slice(0, 9); f.unl = false; f.budget = d === '' ? null : parseInt(d, 10); e.target.value = fmtBudget(f.budget); syncChips(); save(); } });
    box1.appendChild(el('div', { class: 'ga-row' }, [
      el('div', { class: 'ga-tile' }, [el('label', { class: 'ga-lbl', for: 'gaFree', text: 'Thời gian rảnh' }), sel]),
      el('div', { class: 'ga-tile' }, [el('label', { class: 'ga-lbl', for: 'gaBudget', text: 'Ngân sách (VNĐ)' }), inp])
    ]));
    function isOn(b) { return b[0] === null ? f.unl : f.budget === b[0]; }
    var chips = el('div', { class: 'ga-chips', id: 'gaChips' }, BUDGETS.map(function (b) {
      return el('button', { type: 'button', class: 'ga-chip' + (isOn(b) ? ' on' : ''), 'data-v': b[0] === null ? '' : b[0],
        onclick: function () { f.budget = b[0]; f.unl = b[0] === null; inp.value = fmtBudget(f.budget); syncChips(); save(); } }, [b[1]]);
    }));
    function syncChips() { Array.prototype.forEach.call(chips.children, function (c) { c.classList.toggle('on', (c.dataset.v === '' ? f.unl : f.budget === parseInt(c.dataset.v, 10))); }); }
    box1.appendChild(chips);
    wrap.appendChild(box1);

    var box2 = el('div', { class: 'ga-box' });
    box2.appendChild(el('span', { class: 'ga-lbl', text: 'Bạn muốn làm gì? (chọn 1 hoặc nhiều)' }));
    var needs = el('div', { class: 'ga-needs', role: 'group', 'aria-label': 'Nhu cầu' });
    ['an_uong', 'giai_tri', 'tham_quan'].forEach(function (g) {
      needs.appendChild(el('button', { type: 'button', class: 'ga-need' + (f.needs[g] ? ' on' : ''), 'aria-pressed': f.needs[g] ? 'true' : 'false',
        onclick: function (e) { f.needs[g] = !f.needs[g]; e.currentTarget.classList.toggle('on', f.needs[g]); e.currentTarget.setAttribute('aria-pressed', f.needs[g] ? 'true' : 'false'); save(); } },
        [GRP_ICON[g][0] + ' ' + GRP_LABEL[g]]));
    });
    box2.appendChild(needs);
    box2.appendChild(el('span', { class: 'ga-lbl', style: 'margin-top:8px', text: 'Phương tiện di chuyển' }));
    var veh = el('div', { class: 'ga-veh', role: 'radiogroup', 'aria-label': 'Phương tiện' });
    [['walk', 'Đi bộ'], ['bike', 'Xe đạp'], ['motorbike', 'Xe máy'], ['car', 'Ô tô'], ['bus', 'Xe buýt']].forEach(function (v) {
      var b = el('button', { type: 'button', class: 'ga-v1' + (f.vehicle === v[0] ? ' on' : ''), role: 'radio', 'aria-checked': f.vehicle === v[0] ? 'true' : 'false',
        onclick: function () { f.vehicle = v[0]; Array.prototype.forEach.call(veh.children, function (c) { var on = c.dataset.v === v[0]; c.classList.toggle('on', on); c.setAttribute('aria-checked', on ? 'true' : 'false'); }); save(); }, 'data-v': v[0] },
        [VEH_ICON[v[0]] + ' ' + v[1], v[0] === 'bus' ? el('small', { text: '(ước lượng)' }) : null]);
      veh.appendChild(b);
    });
    box2.appendChild(veh);
    wrap.appendChild(box2);

    wrap.appendChild(el('button', { type: 'button', class: 'ga-go', disabled: S.running, onclick: function () {
      var err = validate(); if (err) { S.error = err; return render(); }
      runSearch(buildQuery());
    } }, ['✦ Khám phá quanh bạn']));
    wrap.appendChild(el('div', { class: 'ga-tag', text: 'Có thời gian rảnh? Để GEs dẫn lối! ⭐' }));
    return wrap;
  }

  function viewPicker() {
    var box = el('div', { class: 'ga-pick' });
    var inp = el('input', { type: 'text', placeholder: 'Tìm khu vực, địa danh…', 'aria-label': 'Tìm khu vực', autocomplete: 'off', value: S.pickQ,
      oninput: function (e) { S.pickQ = e.target.value; fillList(); } });
    var list = el('div', { class: 'ga-plist', role: 'listbox' });
    box.appendChild(inp); box.appendChild(list);
    function fold(s) { return s.toLowerCase().replace(/đ/g, 'd').normalize('NFD').replace(/[̀-ͯ]/g, ''); }
    function fillList() {
      list.textContent = '';
      if (S.metaErr) return list.appendChild(el('div', { class: 'ga-hint', style: 'padding:10px 14px', text: S.metaErr }));
      if (!S.meta) return list.appendChild(el('div', { class: 'ga-hint', style: 'padding:10px 14px', text: 'Đang tải danh sách…' }));
      var q = fold(S.pickQ.trim()), last = null, n = 0;
      S.meta.areas.forEach(function (a) {
        if (q && fold(a.name + ' ' + a.group).indexOf(q) < 0) return;
        if (a.group !== last) { list.appendChild(el('div', { class: 'ga-pgrp', text: a.group })); last = a.group; }
        n++;
        list.appendChild(el('button', { type: 'button', class: 'ga-pit', role: 'option', 'aria-selected': (!S.form.gps && S.form.areaId === a.id) ? 'true' : 'false', text: a.name,
          onclick: function () { S.form.areaId = a.id; S.form.gps = null; S.pickOpen = false; save(); render(); } }));
      });
      if (!n) list.appendChild(el('div', { class: 'ga-hint', style: 'padding:10px 14px', text: 'Không có khu vực nào khớp. Hiện chỉ hỗ trợ TP.HCM mới.' }));
    }
    fillList();
    return box;
  }

  function useGps() {
    if (!navigator.geolocation) { S.error = 'Trình duyệt không hỗ trợ định vị.'; return render(); }
    S.gpsBusy = true; S.error = ''; render();
    navigator.geolocation.getCurrentPosition(function (p) {
      S.gpsBusy = false; S.form.gps = { lat: p.coords.latitude, lng: p.coords.longitude }; S.pickOpen = false; render();
    }, function (e) {
      S.gpsBusy = false; S.error = e && e.code === 1 ? 'Bạn chưa cho phép truy cập vị trí. Hãy chọn khu vực trong danh sách.' : 'Không lấy được vị trí. Hãy chọn khu vực trong danh sách.'; render();
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  }

  function viewResults() {
    var r = S.result, q = r.query, v = S.form.vehicle && r.vehicles[S.form.vehicle] ? S.form.vehicle : q.vehicle;
    var data = r.vehicles[v], wrap = el('div');
    wrap.appendChild(el('div', { class: 'ga-sum' }, [
      el('span', { text: '📍 ' + r.origin.name }), el('span', { text: '⏱ ' + freeLabel(q.free_minutes) }),
      el('span', { text: '💰 ' + (q.budget === null ? 'Không giới hạn' : fmtBudget(q.budget) + 'đ') })
    ]));
    var seg = el('div', { class: 'ga-seg', role: 'tablist', 'aria-label': 'Phương tiện' });
    r.vehicle_order.slice().sort(function (a, b) { return ['walk', 'bike', 'motorbike', 'car', 'bus'].indexOf(a) - ['walk', 'bike', 'motorbike', 'car', 'bus'].indexOf(b); }).forEach(function (id) {
      var label = r.vehicles[id].label;
      seg.appendChild(el('button', { type: 'button', role: 'tab', class: 'ga-sg' + (id === v ? ' on' : ''), 'aria-selected': id === v ? 'true' : 'false',
        onclick: function () { S.form.vehicle = id; q.vehicle = id; save(); render(); } }, [VEH_ICON[id] + ' ' + label]));
    });
    wrap.appendChild(seg);
    wrap.appendChild(el('div', { class: 'ga-found' }, [el('span', { text: data.total ? 'Tìm thấy ' + data.total + ' nơi phù hợp' : 'Chưa có nơi phù hợp' }), el('small', { text: 'Sắp xếp: nổi bật, rồi gần nhất' })]));
    var list = el('div', { class: 'ga-list' });
    if (!data.total) {
      list.appendChild(el('div', { class: 'ga-empty', text: 'Với thời gian rảnh và phương tiện này, GEs chưa tìm được nơi đi–chơi–về kịp. Thử thêm thời gian, tăng ngân sách hoặc đổi phương tiện nhé.' }));
    } else {
      q.needs.forEach(function (g) {
        var items = data.groups[g] || [];
        if (!items.length) return;
        if (q.needs.length > 1) list.appendChild(el('div', { class: 'ga-gh', text: GRP_ICON[g][0] + ' ' + (r.group_label[g] || g) + ' (' + items.length + ')' }));
        items.forEach(function (it) { list.appendChild(card(it, v)); });
      });
    }
    wrap.appendChild(list);
    wrap.appendChild(el('button', { type: 'button', class: 'ga-new', onclick: function () { S.view = 'form'; S.error = ''; S.pickOpen = false; render(); } }, ['↺ Tìm kiếm mới']));
    wrap.appendChild(el('div', { class: 'ga-foot', text: 'Thời gian di chuyển là ước tính (có thể lệch vài phút theo giao thông). Giá là ước tính theo loại hình, không phải giá niêm yết. ' + (r.attribution || '') }));
    return wrap;
  }

  function card(it, v) {
    var g = GRP_ICON[it.grp] || GRP_ICON.tham_quan, icon = g[0];
    if (/cà phê/i.test(it.kind)) icon = '☕';
    var meta = it.kind + (it.addr ? ' · ' + it.addr : '');
    var dir = el('a', { class: 'ga-bt', href: '#', target: '_blank', rel: 'noopener noreferrer', 'aria-label': 'Chỉ đường tới ' + it.name }, ['Chỉ đường ↗']);
    if (/^https:\/\/www\.google\.com\/maps\/dir\/\?/.test(it.directions)) dir.setAttribute('href', it.directions); else dir.removeAttribute('href');
    return el('div', { class: 'ga-rc' }, [
      el('div', { class: 'ga-ic ' + g[1], text: icon, 'aria-hidden': 'true' }),
      el('div', { class: 'ga-tx' }, [
        el('div', { class: 'ga-nm', text: it.name }),
        el('div', { class: 'ga-mt', text: meta }),
        el('div', { class: 'ga-st', title: 'Đi + chơi + về khoảng ' + it.total_min + ' phút', text: VEH_ICON[v] + ' ' + it.travel_min + ' phút · ' + costText(it.cost) })
      ]), dir
    ]);
  }

  /* ---------- khởi động ---------- */
  $fab.addEventListener('click', function () { setOpen(!S.open); });
  $close.addEventListener('click', function () { setOpen(false); $fab.focus(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && S.open) { setOpen(false); $fab.focus(); } });

  window.addEventListener('pagehide', function () { S.unloading = true; });
  window.addEventListener('beforeunload', function () { S.unloading = true; });
  try {                                                                    // F5 / tải lại trang = bắt đầu mới (xoá kết quả + ô đã nhập)
    var nav = performance.getEntriesByType('navigation')[0];
    if (nav && nav.type === 'reload') sessionStorage.removeItem(KEY);
  } catch (e) {}
  load();
  S.view = S.running ? 'loading' : (S.result ? 'results' : 'form');
  updateFab();
  if (S.running && S.pending) { ensureMeta(); runSearch(S.pending); }      // chuyển trang giữa chừng → chạy lại (tính rất nhanh)
  else if (S.running) { S.running = false; save(); updateFab(); }
})();
