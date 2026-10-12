// editor.js — khung kéo thả cảm ứng (SVG mặt bằng, đơn vị mm, mặt tiền ở dưới: y_svg = D − y_lô).
// Một ngón: kéo khối đang chọn = dời, kéo tay nắm = co giãn, kéo cửa đang chọn = dời cửa, kéo chỗ khác = trượt khung nhìn; chạm = chọn.
// Hai ngón: chụm / mở = phóng to / nhỏ. Chuột: lăn = phóng. Bóng khối khi kéo hỏi C# (Ghost, đồng bộ) để bám mép đúng như lõi Dtool.
// Trang hiện trạng (svg có #sv-gmin): lưới chia nhỏ dần theo mức phóng; data-draw="1" = đang vẽ phòng → một ngón đặt góc (tâm ngắm bám lưới,
// C# DrawSnap / DrawAt), hai ngón kéo / phóng; chấm góc "scorner" kéo = dời góc (CornerSnap / CornerDrop).
const STEPS = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000];
export function init(svg, dn) {
  const st = { svg, dn, vb: null, ptrs: new Map(), mode: null, start: null, hit: null, last: null, pinch: null, raf: 0 };
  const W = () => +svg.dataset.w, D = () => +svg.dataset.d;
  const ghost = () => svg.querySelector("#ghost");

  function apply() {
    const v = st.vb; if (!v) return;
    svg.setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
    handles();
  }
  function fit() {
    const m = 600, w = W() + 2 * m, h = D() + 2 * m;
    st.vb = { x: -m, y: -m, w, h }; apply();
  }
  function mmpp() { const c = svg.getScreenCTM(); return c && c.a ? 1 / c.a : 10; }
  function toSvg(cx, cy) {
    const c = svg.getScreenCTM(); if (!c) return { x: 0, y: 0 };
    const p = new DOMPoint(cx, cy).matrixTransform(c.inverse()); return { x: p.x, y: p.y };
  }
  const toModel = p => ({ x: p.x, y: D() - p.y });
  function handles() {   // tay nắm, vòng cửa: cỡ cố định theo điểm ảnh
    const k = mmpp();
    // khối: 11 px; đồ nội thất: 8 px (món nhỏ trên màn hình không bị chấm che hết)
    svg.querySelectorAll("circle.handle").forEach(c => c.setAttribute("r", ((c.classList.contains("fh") ? 8 : 11) * k).toFixed(1)));
    svg.style.setProperty("--mmpp", k);
    // vùng chạm số đo cạnh (hiện trạng): không nhỏ hơn 56 × 30 px dù đang thu nhỏ
    svg.querySelectorAll("rect.dim-hit").forEach(r => {
      const w = Math.max(+r.dataset.w || 0, 56 * k), h = Math.max(+r.dataset.h || 0, 30 * k);
      r.setAttribute("x", (-w / 2).toFixed(1)); r.setAttribute("y", (-h / 2).toFixed(1)); r.setAttribute("width", w.toFixed(1)); r.setAttribute("height", h.toFixed(1));
    });
    grid();
  }
  // ---------- lưới (trang hiện trạng) ----------
  function gridStep() {
    const lk = +(svg.dataset.step || 0); if (lk > 0) return lk;
    const k = mmpp(); for (const s of STEPS) if (s / k >= 14) return s; return STEPS[STEPS.length - 1];
  }
  function grid() {
    const pm = svg.querySelector("#sv-gmin"), pM = svg.querySelector("#sv-gmaj"); if (!pm || !pM) return;
    const k = mmpp(), s = gridStep(), big = s < 1000 ? 1000 : s * 5, gx = +(svg.dataset.gx || 0), gy = +(svg.dataset.gy || 0);
    const set = (pat, step, minPx, w) => {
      pat.setAttribute("width", step); pat.setAttribute("height", step); pat.setAttribute("x", gx); pat.setAttribute("y", D() - gy);
      const p = pat.firstElementChild; p.setAttribute("d", step / k >= minPx ? `M${step} 0 L0 0 0 ${step}` : ""); p.setAttribute("stroke-width", (w * k).toFixed(2));
    };
    set(pm, s, 5, 1); set(pM, big, 8, 1.3);
    const b = svg.parentElement && svg.parentElement.querySelector(".grid-btn");
    if (b) b.dataset.lbl = "Lưới " + (s >= 1000 ? (s / 1000).toString().replace(".", ",") + " m" : s + " mm");
  }
  // ---------- tâm ngắm (vẽ phòng / dời góc) ----------
  const cur = id => svg.querySelector("#" + id);
  function showCursor(r) {
    const g = cur("sv-cur"), ro = svg.parentElement && svg.parentElement.querySelector(".sv-readout");
    if (!g) return;
    if (!r) { g.style.display = "none"; if (ro) ro.hidden = true; return; }      // display (không phải visibility: nét con đặt visible sẽ vẫn hiện)
    const v = st.vb, y = D() - r.y, k = mmpp();
    const L = (id, on, x1, y1, x2, y2) => { const e = cur(id); if (!e) return; e.setAttribute("visibility", on ? "visible" : "hidden"); if (on) { e.setAttribute("x1", x1); e.setAttribute("y1", y1); e.setAttribute("x2", x2); e.setAttribute("y2", y2); } };
    L("sv-cur-h", true, v.x, y, v.x + v.w, y); L("sv-cur-v", true, r.x, v.y, r.x, v.y + v.h);
    L("sv-cur-a", r.na >= 1, r.ax, D() - r.ay, r.x, y); L("sv-cur-b", r.na >= 2, r.x, y, r.bx, D() - r.by);
    const cb = cur("sv-cur-b"); if (cb) cb.setAttribute("class", r.solid ? "cur-rub" : "cur-rub close");
    const p = cur("sv-cur-p"); p.setAttribute("cx", r.x); p.setAttribute("cy", y); p.setAttribute("r", ((r.kind > 0 ? 9 : 6) * k).toFixed(1));
    p.setAttribute("class", "cur-p k" + r.kind);
    g.style.display = "inline";
    if (ro) { ro.textContent = r.txt || ""; ro.hidden = !r.txt; }
  }
  function preview(q) {
    let r = null;
    try {
      r = st.mode === "corner" ? dn.invokeMethod("CornerSnap", st.hit.id, q.x, q.y, gridStep(), mmpp())
        : dn.invokeMethod("DrawSnap", q.x, q.y, gridStep(), mmpp());
    } catch (err) { console.error(err); }
    showCursor(r);
  }
  function zoomAt(p, f) {
    // giới hạn theo độ phân giải (màn hình dọc: chiều cao quyết định tỉ lệ) — phóng tới ~0,8 mm / điểm ảnh để lưới chia tới 10 mm
    const v = st.vb, maxW = 4 * (W() + D()) + 4000, k = mmpp();
    f = Math.max(f, 0.8 / k); if (v.w * f > maxW) f = maxW / v.w;
    v.x = p.x - (p.x - v.x) * f; v.y = p.y - (p.y - v.y) * f; v.w *= f; v.h *= f;
  }
  function showGhost(r) {
    const g = ghost(); if (!g) return;
    if (!r) { g.setAttribute("visibility", "hidden"); return; }
    g.setAttribute("x", r[0]); g.setAttribute("y", D() - r[3]); g.setAttribute("width", Math.max(0, r[2] - r[0])); g.setAttribute("height", Math.max(0, r[3] - r[1]));
    g.setAttribute("visibility", "visible");
  }
  function hitOf(target) {
    const h = target && target.closest ? target.closest("[data-hit]") : null;
    if (!h) return null;
    return { kind: h.dataset.hit, id: h.dataset.id || "", edge: +(h.dataset.edge || 0), sel: h.dataset.sel === "1" || h.classList.contains("sel") };
  }

  function down(e) {
    try { svg.setPointerCapture(e.pointerId); } catch (err) { }
    st.ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (st.ptrs.size === 2) {           // bắt đầu chụm: bỏ kéo đang dở
      if (st.mode === "drag") showGhost(null);
      showCursor(null);
      const [a, b] = [...st.ptrs.values()];
      st.mode = "pinch"; st.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), m: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 } };
      return;
    }
    if (st.ptrs.size > 2) return;
    st.mode = "press"; st.hit = hitOf(e.target);
    const p = toSvg(e.clientX, e.clientY);
    st.start = { cx: e.clientX, cy: e.clientY, svg: p, model: toModel(p), t: performance.now() };
    e.preventDefault();
    if (st.hit && st.hit.kind === "scorner") st.mode = "corner";            // chấm góc phòng: kéo = dời góc
    else if (svg.dataset.draw === "1") st.mode = "draw";                  // đang vẽ phòng: ngón đặt lên = tâm ngắm
    if (st.mode === "corner" || st.mode === "draw") preview(st.start.model);
  }
  function move(e) {
    if (!st.ptrs.has(e.pointerId)) return;
    st.ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (st.mode === "pinch" && st.ptrs.size >= 2) {
      const [a, b] = [...st.ptrs.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y), m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const p = toSvg(st.pinch.m.x, st.pinch.m.y);
      zoomAt(p, st.pinch.d / Math.max(1, d)); apply();
      const p2 = toSvg(m.x, m.y); st.vb.x += p.x - p2.x; st.vb.y += p.y - p2.y; apply();
      st.pinch = { d, m }; return;
    }
    if (!st.start) return;
    if (st.mode === "draw" || st.mode === "corner") {
      st.last = toModel(toSvg(e.clientX, e.clientY));
      if (!st.raf) st.raf = requestAnimationFrame(() => { st.raf = 0; if ((st.mode === "draw" || st.mode === "corner") && st.last) preview(st.last); });
      return;
    }
    const moved = Math.hypot(e.clientX - st.start.cx, e.clientY - st.start.cy) > 7;
    if (st.mode === "press" && moved) {
      const h = st.hit;
      st.mode = h && (h.kind === "handle" || h.kind === "fhandle" || h.sel) ? "drag" : "pan";   // món đang chọn (khối, cửa, đồ, phòng / cột / ghi chú hiện trạng) → kéo
    }
    if (st.mode === "pan") {
      const p = toSvg(e.clientX, e.clientY);
      st.vb.x += st.start.svg.x - p.x; st.vb.y += st.start.svg.y - p.y; apply();
    } else if (st.mode === "drag") {
      const q = toModel(toSvg(e.clientX, e.clientY)); st.last = q;
      if (!st.raf) st.raf = requestAnimationFrame(() => {
        st.raf = 0; if (st.mode !== "drag" || !st.last) return;
        let r = null;
        try { r = dn.invokeMethod("Ghost", st.hit.kind, st.hit.id, st.hit.edge, st.start.model.x, st.start.model.y, st.last.x, st.last.y, mmpp()); } catch (err) { console.error(err); }
        showGhost(r);
      });
    }
  }
  function up(e) {
    if (!st.ptrs.has(e.pointerId)) return;
    st.ptrs.delete(e.pointerId);
    if (st.mode === "pinch") { if (st.ptrs.size === 0) { st.mode = null; st.start = null; } return; }
    const mode = st.mode; st.mode = null;
    if (!st.start) return;
    const q = toModel(toSvg(e.clientX, e.clientY)), h = st.hit, s = st.start; st.start = null;
    if (mode === "draw") { showCursor(null); dn.invokeMethodAsync("DrawAt", q.x, q.y, gridStep(), mmpp()); return; }
    if (mode === "corner") { showCursor(null); dn.invokeMethodAsync("CornerDrop", h.id, q.x, q.y, gridStep(), mmpp()); return; }
    if (mode === "drag") { showGhost(null); dn.invokeMethodAsync("Drop", h.kind, h.id, h.edge, s.model.x, s.model.y, q.x, q.y, mmpp()); }
    else if (mode === "press") dn.invokeMethodAsync("Tap", h ? h.kind : "", h ? h.id : "", q.x, q.y, mmpp());
  }
  function cancel(e) { st.ptrs.delete(e.pointerId); if (st.mode === "drag") showGhost(null); showCursor(null); st.mode = null; st.start = null; }
  function wheel(e) {
    e.preventDefault();
    zoomAt(toSvg(e.clientX, e.clientY), Math.exp(e.deltaY * 0.0015)); apply();
  }
  function dbl(e) { if (svg.dataset.draw !== "1" && !hitOf(e.target)) fit(); }   // đang vẽ: chạm nhanh hai góc không được làm khung nhảy

  svg.addEventListener("pointerdown", down);
  svg.addEventListener("pointermove", move);
  svg.addEventListener("pointerup", up);
  svg.addEventListener("pointercancel", cancel);
  svg.addEventListener("wheel", wheel, { passive: false });
  svg.addEventListener("dblclick", dbl);
  const ro = new ResizeObserver(() => handles()); ro.observe(svg);
  fit();

  return {
    fit,
    refresh() { handles(); },
    /** Tâm khung nhìn (hệ lô, mm) — chỗ thả khối mới. */
    center() { const r = svg.getBoundingClientRect(); const p = toModel(toSvg(r.left + r.width / 2, r.top + r.height * 0.45)); return [p.x, p.y]; },
    /** Toạ độ (px) của điểm hệ lô trong khung chứa mặt bằng — đặt ô nhập nổi; kẹp trong khung. */
    screenOf(x, y) {
      const c = svg.getScreenCTM(), box = (svg.parentElement || svg).getBoundingClientRect(); if (!c) return [box.width / 2, box.height / 2];
      const p = new DOMPoint(x, D() - y).matrixTransform(c);
      return [Math.min(box.width - 110, Math.max(110, p.x - box.left)), Math.min(box.height - 20, Math.max(84, p.y - box.top))];
    },
    /** Đưa điểm (hệ lô) vào giữa khung nhìn nếu đang ở ngoài. */
    show(x, y) { const v = st.vb, sy = D() - y; if (x < v.x || x > v.x + v.w || sy < v.y || sy > v.y + v.h) { v.x = x - v.w / 2; v.y = sy - v.h / 2; apply(); } },
    dispose() { ro.disconnect(); svg.removeEventListener("pointerdown", down); svg.removeEventListener("pointermove", move); svg.removeEventListener("pointerup", up); svg.removeEventListener("pointercancel", cancel); svg.removeEventListener("wheel", wheel); svg.removeEventListener("dblclick", dbl); }
  };
}

// ---------- file ----------
export function download(name, text) {
  const blob = new Blob([text], { type: "application/json" }), a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
/** Chia sẻ file (Zalo, Drive… trên điện thoại); không hỗ trợ thì tải về. Trả "share" / "download" / "cancel". */
export async function share(name, text) {
  try {
    const f = new File([text], name, { type: "application/json" });
    if (navigator.canShare && navigator.canShare({ files: [f] })) { await navigator.share({ files: [f], title: name }); return "share"; }
  } catch (e) { if (e && e.name === "AbortError") return "cancel"; }
  download(name, text); return "download";
}
export function openViewer(json) { try { sessionStorage.setItem("mbtd.scene", json); } catch (e) { } }
/** Đưa con trỏ vào ô (vd. ô dài cạnh khi đi tường) và chọn chữ. */
/** Bật / tắt toàn màn hình (gọi trong lần chạm của người dùng). "on" / "off"; "no" = trình duyệt không cho (iPhone Safari). */
export async function fullscreen() {
  const d = document, el = d.documentElement;
  if (d.fullscreenElement || d.webkitFullscreenElement) { try { await (d.exitFullscreen || d.webkitExitFullscreen).call(d); } catch (e) { } return "off"; }
  const rq = el.requestFullscreen || el.webkitRequestFullscreen;
  if (!rq || d.fullscreenEnabled === false) return "no";
  try { await rq.call(el, { navigationUI: "hide" }); return "on"; } catch (e) { return "no"; }
}
export function focusSel(sel) { setTimeout(() => { const e = document.querySelector(sel); if (e) { e.focus(); if (e.select) e.select(); } }, 30); }
