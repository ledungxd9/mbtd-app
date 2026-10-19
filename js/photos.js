// photos.js — ảnh khảo sát hiện trạng: lưu trong IndexedDB của trình duyệt (localStorage chỉ ~5 MB, không chứa nổi ảnh), mã ảnh ghi trong
// ghi chú (SvNote.Photos). Ảnh thu nhỏ ≤ 1600 px, JPEG 0,78 (~200–400 KB). Gửi file .mbtd thì ảnh đi kèm trong Extra["photos"] (AppState).
const DB = "mbtd-photos", ST = "photos";
let dbp = null;
function db() {
  return dbp || (dbp = new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(ST);
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  }));
}
async function tx(mode, fn) {
  const d = await db();
  return new Promise((res, rej) => { const t = d.transaction(ST, mode); const s = t.objectStore(ST); const out = fn(s); t.oncomplete = () => res(out && out.result !== undefined ? out.result : out); t.onerror = () => rej(t.error); });
}
export async function put(id, url) { await tx("readwrite", s => s.put(url, id)); }
export async function get(id) { try { return (await tx("readonly", s => s.get(id))) || null; } catch (e) { return null; } }
export async function del(id) { try { await tx("readwrite", s => s.delete(id)); } catch (e) { } }
/** {mã: dataURL} của các mã có trong máy (gửi file). */
export async function getMany(ids) { const o = {}; for (const id of ids || []) { const u = await get(id); if (u) o[id] = u; } return o; }
/** Nạp ảnh từ file .mbtd mở được ({mã: dataURL}). */
export async function putMany(map) { let n = 0; for (const id of Object.keys(map || {})) { await put(id, map[id]); n++; } return n; }

async function shrink(file, max, q) {
  let src; try { src = await createImageBitmap(file, { imageOrientation: "from-image" }); } catch (e) { src = null; }
  if (!src) src = await new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = URL.createObjectURL(file); });
  const w0 = src.width, h0 = src.height, k = Math.min(1, max / Math.max(w0, h0));
  const c = document.createElement("canvas"); c.width = Math.max(1, Math.round(w0 * k)); c.height = Math.max(1, Math.round(h0 * k));
  c.getContext("2d").drawImage(src, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", q);
}
/** Chụp (CAMERA = true, camera sau) hoặc chọn ảnh; thu nhỏ, lưu IndexedDB; trả các mã ảnh mới ([] nếu bỏ). */
export function pick(camera) {
  return new Promise(res => {
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    if (camera) inp.setAttribute("capture", "environment"); else inp.multiple = true;
    let done = false;
    inp.addEventListener("change", async () => {
      done = true; const out = [];
      for (const f of inp.files || []) {
        try { const url = await shrink(f, 1600, 0.78); const id = "p" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); await put(id, url); out.push(id); } catch (e) { console.error(e); }
      }
      res(out);
    });
    inp.addEventListener("cancel", () => { if (!done) res([]); });
    inp.click();
  });
}
