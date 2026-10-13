/* Manifest version: QI13zw/9 */
// Caution! Be sure you understand the caveats before publishing an application with
// offline support. See https://aka.ms/blazor-offline-considerations

self.importScripts('./service-worker-assets.js');
self.addEventListener('install', event => event.waitUntil(onInstall(event)));
self.addEventListener('activate', event => event.waitUntil(onActivate(event)));
self.addEventListener('fetch', event => event.respondWith(onFetch(event)));

const cacheNamePrefix = 'offline-cache-';
const cacheName = `${cacheNamePrefix}${self.assetsManifest.version}`;
const offlineAssetsInclude = [ /\.dll$/, /\.pdb$/, /\.wasm/, /\.html/, /\.js$/, /\.json$/, /\.css$/, /\.woff$/, /\.png$/, /\.jpe?g$/, /\.gif$/, /\.ico$/, /\.blat$/, /\.dat$/, /\.webmanifest$/ ];
const offlineAssetsExclude = [ /^service-worker\.js$/ ];

// Gốc = thư mục chứa service-worker.js (GitHub Pages: /mbtd-app/). Gốc "/" cố định của mẫu Blazor làm viewer3d.html (khung 3D) không khớp
// danh sách tệp → bị trả index.html → "Not Found" (người dùng 2026-10-05, điện thoại).
const baseUrl = new URL('./', self.location.href);
const manifestUrlList = self.assetsManifest.assets.map(asset => new URL(asset.url, baseUrl).href);
const noQuery = u => { const x = new URL(u); x.search = ''; x.hash = ''; return x.href; };

// Hosting dtool.vn (iNET OneShield) chèn <meta data-osh-rid…><script src="/_osh/collect.js"…></script> vào MỌI trang HTML, mỗi lần một mã khác
// → so integrity luôn sai → service worker mới không cài được, máy đã cài app kẹt ở bản cũ (người dùng 2026-10-12 "vẫn chưa thấy phiên bản mới";
// trình duyệt mới thì vẫn thấy bản mới vì tải thẳng từ mạng). HTML: tải không kèm integrity, bỏ đoạn chèn, so mã băm phần còn lại (khớp với bản build),
// lưu bản đã bỏ. Định dạng chèn đổi mà không khớp nữa → vẫn lưu (ghi cảnh báo) để app không kẹt bản cũ.
const oshStrip = s => s.replace(/<meta data-osh-rid[^>]*>/g, '').replace(/<script[^>]*src="\/_osh\/[^"]*"[^>]*><\/script>/g, '');
async function sha256(buf) {
    const d = new Uint8Array(await crypto.subtle.digest('SHA-256', buf)); let b = '';
    for (let i = 0; i < d.length; i++) b += String.fromCharCode(d[i]);
    return 'sha256-' + btoa(b);
}
async function cacheHtml(cache, asset) {
    const r = await fetch(new Request(asset.url, { cache: 'no-cache' }));
    if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + asset.url);
    const bytes = new TextEncoder().encode(oshStrip(await r.text()));
    if (await sha256(bytes) !== asset.hash) console.warn('Service worker: ' + asset.url + ' khác mã băm bản build — vẫn lưu');
    await cache.put(asset.url, new Response(bytes, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
}

async function onInstall(event) {
    console.info('Service worker: Install');
    self.skipWaiting();                       // bản mới chạy ngay lần mở sau, không chờ đóng hết thẻ

    // Fetch and cache all matching items from the assets manifest
    const assets = self.assetsManifest.assets
        .filter(asset => offlineAssetsInclude.some(pattern => pattern.test(asset.url)))
        .filter(asset => !offlineAssetsExclude.some(pattern => pattern.test(asset.url)));
    const isHtml = asset => /\.html$/.test(asset.url);
    const cache = await caches.open(cacheName);
    await cache.addAll(assets.filter(a => !isHtml(a)).map(asset => new Request(asset.url, { integrity: asset.hash, cache: 'no-cache' })));
    await Promise.all(assets.filter(isHtml).map(asset => cacheHtml(cache, asset)));
}

async function onActivate(event) {
    console.info('Service worker: Activate');

    // Delete unused caches
    const cacheKeys = await caches.keys();
    await Promise.all(cacheKeys
        .filter(key => key.startsWith(cacheNamePrefix) && key !== cacheName)
        .map(key => caches.delete(key)));
    await self.clients.claim();
}

async function onFetch(event) {
    let cachedResponse = null;
    if (event.request.method === 'GET') {
        // For all navigation requests, try to serve index.html from cache,
        // unless that request is for an offline resource.
        // If you need some URLs to be server-rendered, edit the following check to exclude those URLs
        const shouldServeIndexHtml = event.request.mode === 'navigate'
            && !manifestUrlList.includes(noQuery(event.request.url));

        const request = shouldServeIndexHtml ? 'index.html' : event.request;
        const cache = await caches.open(cacheName);
        cachedResponse = await cache.match(request);
    }

    return cachedResponse || fetch(event.request);
}

// build 20261013-113414 701dcd7 dtool.vn
