<?php
// MBTD-UPDATER v3 — cập nhật dtool.vn từ GitHub (kho công khai ledungxd9/mbtd-app). Nguồn: Dtool\Mobile\tools\dtoolvn\update.php.
// Người dùng 2026-10-06: "em có thể tự cập nhật lên hosting không" → chọn "Hosting tự lấy từ GitHub" (không đưa mật khẩu hosting cho ai);
// "cho web tự cập nhật luôn" → v2 thêm website + tự cập nhật script này.
// Chạy bằng cron (curl https://dtool.vn/_mbtd/update.php) hoặc gọi URL sau khi đẩy bản mới. KHÔNG nhận tham số.
//  1. Script: so với `_mbtd/update.php` của nhánh `website`; khác → kiểm (dấu MBTD-UPDATER, cú pháp PHP qua token_get_all TOKEN_PARSE) → thay (lượt sau dùng).
//  2. App (/app): nhánh `dtoolvn` — so BUILD.txt, tải zip → app.new → kiểm index.html / _framework / .htaccess / BUILD → đổi tên app → app.old, app.new → app.
//  3. Website (thư mục gốc): nhánh `website` — so WEB_BUILD.txt với _mbtd/web_build.txt, tải zip → CHỈ chép index.html, robots.txt, sitemap.xml,
//     *.pdf ở gốc, assets/** (index.html chép sau cùng). KHÔNG đụng .htaccess gốc, /api, /app, /_mbtd, /.well-known; không xóa file cũ.
//  4. Bộ cài Dtool (/tai, v3 — người dùng 2026-10-06 "anh cần đẩy bộ cài cập nhật lên web"; nguồn tools\deploy_setup.ps1): SETUP.json ở gốc nhánh
//     `website` ghi bản, tên file, URL tài sản GitHub Release (chỉ nhận github.com/<REPO>/releases/download/…), dung lượng, sha256 → tải thẳng ra đĩa
//     (_mbtd/setup.part), kiểm dung lượng + sha256 → /tai/<file> + /tai/setup.json (công khai: bản, file, dung lượng, sha256, ngày); giữ bản liền trước,
//     xóa bộ cài cũ hơn. Chạy TRƯỚC mục 3: bộ cài chưa xong thì website chờ (không chép index.html có liên kết hỏng).
header('Content-Type: text/plain; charset=utf-8');
header('Cache-Control: no-store');
@set_time_limit(900);
@ignore_user_abort(true);
$REPO = 'ledungxd9/mbtd-app';
$here = __DIR__; $root = dirname($here); $app = $root . '/app';
$stateF = $here . '/state.json'; $logF = $here . '/update.log';

function say($m) { global $logF; $l = date('Y-m-d H:i:s') . ' ' . $m; echo $l . "\n"; @file_put_contents($logF, $l . "\n", FILE_APPEND); }
function get($url) {
  if (function_exists('curl_init')) {
    $c = curl_init($url);
    curl_setopt_array($c, array(CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true, CURLOPT_MAXREDIRS => 5, CURLOPT_CONNECTTIMEOUT => 30,
      CURLOPT_TIMEOUT => 240, CURLOPT_USERAGENT => 'dtool-mbtd-updater', CURLOPT_HTTPHEADER => array('Cache-Control: no-cache')));
    $b = curl_exec($c); $code = curl_getinfo($c, CURLINFO_HTTP_CODE); $err = curl_error($c); curl_close($c);
    return array($code, $b === false ? '' : $b, $err);
  }
  $ctx = stream_context_create(array('http' => array('timeout' => 240, 'header' => "User-Agent: dtool-mbtd-updater\r\nCache-Control: no-cache\r\n")));
  $b = @file_get_contents($url, false, $ctx); $code = 0;
  if (isset($http_response_header[0]) && preg_match('#\s(\d{3})\s#', $http_response_header[0], $m)) $code = (int)$m[1];
  return array($code, $b === false ? '' : $b, $b === false ? 'file_get_contents lỗi' : '');
}
// tải thẳng ra file (bộ cài ~60 MB — không giữ trong bộ nhớ); trả array(mã HTTP, lỗi)
function download($url, $dst) {
  @unlink($dst);
  if (function_exists('curl_init')) {
    $fh = @fopen($dst, 'wb'); if (!$fh) return array(0, 'không ghi được ' . basename($dst));
    $c = curl_init($url);
    curl_setopt_array($c, array(CURLOPT_FILE => $fh, CURLOPT_FOLLOWLOCATION => true, CURLOPT_MAXREDIRS => 5, CURLOPT_CONNECTTIMEOUT => 30,
      CURLOPT_TIMEOUT => 780, CURLOPT_USERAGENT => 'dtool-mbtd-updater', CURLOPT_FAILONERROR => true));
    $ok = curl_exec($c); $code = curl_getinfo($c, CURLINFO_HTTP_CODE); $err = curl_error($c); curl_close($c); fclose($fh);
    if (!$ok) @unlink($dst);
    return array($code, $err);
  }
  $ctx = stream_context_create(array('http' => array('timeout' => 780, 'follow_location' => 1, 'header' => "User-Agent: dtool-mbtd-updater\r\n")));
  $in = @fopen($url, 'rb', false, $ctx); if (!$in) return array(0, 'fopen lỗi');
  $out = @fopen($dst, 'wb'); if (!$out) { fclose($in); return array(0, 'không ghi được ' . basename($dst)); }
  $n = stream_copy_to_stream($in, $out); fclose($in); fclose($out);
  return array($n === false ? 0 : 200, $n === false ? 'stream_copy lỗi' : '');
}
function rrm($d) {
  if (!file_exists($d) && !is_link($d)) return;
  if (is_file($d) || is_link($d)) { @unlink($d); return; }
  foreach (scandir($d) as $f) if ($f !== '.' && $f !== '..') rrm($d . '/' . $f);
  @rmdir($d);
}
function raw($branch, $path) { global $REPO; return get("https://raw.githubusercontent.com/$REPO/$branch/$path?t=" . time()); }
// tải zip nhánh, giải nén vào _mbtd/x; trả thư mục gốc của nhánh trong đó (null = lỗi, đã ghi log)
function fetch_branch($branch) {
  global $REPO, $here;
  list($c, $zip, $e) = get("https://codeload.github.com/$REPO/zip/refs/heads/$branch");
  if ($c != 200 || strlen($zip) < 1000) { say("LỖI tải zip $branch ($c, " . strlen($zip) . " byte $e)"); return null; }
  $tmpZ = $here . '/dl.zip'; $tmpX = $here . '/x';
  file_put_contents($tmpZ, $zip); unset($zip);
  rrm($tmpX); @mkdir($tmpX, 0755, true);
  $ok = false;
  if (class_exists('ZipArchive')) { $z = new ZipArchive(); if ($z->open($tmpZ) === true) { $ok = $z->extractTo($tmpX); $z->close(); } }
  if (!$ok && class_exists('PharData')) { try { $p = new PharData($tmpZ); $ok = $p->extractTo($tmpX, null, true); } catch (Exception $ex) { $ok = false; } }
  @unlink($tmpZ);
  if (!$ok) { say('LỖI giải nén (không có ZipArchive / PharData?)'); rrm($tmpX); return null; }
  foreach (scandir($tmpX) as $f) if ($f !== '.' && $f !== '..' && is_dir($tmpX . '/' . $f)) return $tmpX . '/' . $f;
  say("LỖI zip $branch rỗng"); rrm($tmpX); return null;
}

$state = is_file($stateF) ? json_decode(@file_get_contents($stateF), true) : array();
if (!is_array($state)) $state = array();
if (!empty($state['checked']) && time() - $state['checked'] < 45) { echo "bỏ qua: vừa kiểm " . (time() - $state['checked']) . " s trước\n"; exit; }
$lock = fopen($here . '/update.lock', 'c');
if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) { echo "đang chạy ở lượt khác\n"; exit; }
$state['checked'] = time(); @file_put_contents($stateF, json_encode($state));
echo "MBTD-UPDATER v3\n";

// ---------- 1. tự cập nhật script ----------
list($c, $code, $e) = raw('website', '_mbtd/update.php');
if ($c == 200 && strlen($code) > 2000 && strpos($code, 'MBTD-UPDATER v') !== false && $code !== @file_get_contents(__FILE__)) {
  $okSyntax = true;
  if (defined('TOKEN_PARSE')) { try { token_get_all($code, TOKEN_PARSE); } catch (Throwable $ex) { $okSyntax = false; say('script mới lỗi cú pháp, giữ bản cũ: ' . $ex->getMessage()); } }
  if ($okSyntax && @file_put_contents($here . '/update.php.new', $code) !== false && @rename($here . '/update.php.new', __FILE__)) say('ĐÃ THAY script cập nhật (dùng từ lượt sau)');
}

// ---------- 2. app ----------
list($c, $want, $e) = raw('dtoolvn', 'BUILD.txt');
$want = trim($want);
$have = is_file($app . '/BUILD.txt') ? trim(@file_get_contents($app . '/BUILD.txt')) : '';
if ($c != 200 || $want === '' || strlen($want) > 120) say("LỖI đọc BUILD.txt app ($c $e)");
elseif ($have === $want && is_file($app . '/index.html')) echo "app đã mới nhất: $have\n";
elseif ($top = fetch_branch('dtoolvn')) {
  $got = is_file($top . '/BUILD.txt') ? trim(file_get_contents($top . '/BUILD.txt')) : '';
  if (!is_file($top . '/index.html') || !is_dir($top . '/_framework') || !is_file($top . '/.htaccess')) say('LỖI zip app thiếu index.html / _framework / .htaccess');
  elseif ($got !== $want) say("chờ: zip app còn bản $got, BUILD.txt đã là $want (bộ nhớ đệm GitHub) — lượt sau");
  else {
    $new = $root . '/app.new'; $old = $root . '/app.old';
    rrm($new); rrm($old);
    if (!@rename($top, $new)) say('LỖI chuyển bản mới sang app.new');
    elseif (is_dir($app) && !@rename($app, $old)) { say('LỖI đổi tên app → app.old'); rrm($new); }
    elseif (!@rename($new, $app)) { @rename($old, $app); say('LỖI đổi tên app.new → app (đã trả app cũ)'); }
    else { rrm($old); $state['build'] = $want; say('ĐÃ CẬP NHẬT app: ' . ($have === '' ? '(chưa có)' : $have) . " → $want"); }
  }
  rrm($here . '/x');
}

// ---------- 4. bộ cài Dtool (chạy trước website) ----------
$tai = $root . '/tai'; $setupOk = true;
list($c, $sj, $e) = raw('website', 'SETUP.json');
if ($c == 404) echo "bộ cài: chưa có SETUP.json\n";
elseif ($c != 200) { say("LỖI đọc SETUP.json ($c $e)"); $setupOk = false; }
else {
  $S = json_decode($sj, true);
  $valid = is_array($S) && isset($S['ver'], $S['file'], $S['url'], $S['size'], $S['sha256'])
    && preg_match('#^Dtool_CaiDat_[0-9]+(\.[0-9]+){1,3}\.zip$#', $S['file'])
    && strpos($S['url'], "https://github.com/$REPO/releases/download/") === 0 && substr($S['url'], -strlen($S['file'])) === $S['file']
    && is_numeric($S['size']) && $S['size'] > 1000000 && $S['size'] < 500000000 && preg_match('#^[0-9a-f]{64}$#', $S['sha256']);
  if (!$valid) { say('LỖI SETUP.json không hợp lệ — bỏ qua bộ cài'); $setupOk = false; }
  else {
    $have = is_file($tai . '/setup.json') ? json_decode(@file_get_contents($tai . '/setup.json'), true) : null;
    $dst = $tai . '/' . $S['file'];
    if (is_array($have) && isset($have['sha256']) && $have['sha256'] === $S['sha256'] && is_file($dst) && filesize($dst) == $S['size']) echo "bộ cài đã mới nhất: {$S['ver']}\n";
    else {
      if (!is_dir($tai)) @mkdir($tai, 0755, true);
      $ht = "# sinh bởi _mbtd/update.php\nOptions -Indexes\n<IfModule mod_mime.c>\n  AddType application/zip .zip\n  AddType application/json .json\n</IfModule>\n"
          . "<IfModule mod_headers.c>\n  <Files \"setup.json\">\n    Header set Cache-Control \"no-cache\"\n  </Files>\n</IfModule>\n";
      if (@file_get_contents($tai . '/.htaccess') !== $ht) @file_put_contents($tai . '/.htaccess', $ht);
      $part = $here . '/setup.part'; $t0 = time();
      list($dc, $de) = download($S['url'], $part);
      $sz = is_file($part) ? filesize($part) : 0;
      if ($sz != $S['size']) { say("LỖI tải bộ cài {$S['file']} ($dc $de, $sz / {$S['size']} byte, " . (time() - $t0) . ' s) — lượt sau'); @unlink($part); $setupOk = false; }
      elseif (hash_file('sha256', $part) !== $S['sha256']) { say("LỖI bộ cài {$S['file']} sai sha256 — bỏ"); @unlink($part); $setupOk = false; }
      elseif (!@rename($part, $dst)) { say('LỖI chuyển bộ cài vào /tai'); @unlink($part); $setupOk = false; }
      else {
        $prev = (is_array($have) && isset($have['file'])) ? $have['file'] : '';
        $pub = array('ver' => $S['ver'], 'file' => $S['file'], 'size' => (int)$S['size'], 'sha256' => $S['sha256'], 'date' => isset($S['date']) ? $S['date'] : date('Y-m-d'));
        @file_put_contents($tai . '/setup.json', json_encode($pub, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        foreach (glob($tai . '/Dtool_CaiDat_*.zip') as $f) if (basename($f) !== $S['file'] && basename($f) !== $prev) @unlink($f);
        say('ĐÃ CẬP NHẬT bộ cài: ' . ($prev === '' ? '(lần đầu)' : $prev) . " → {$S['file']} ($sz byte, " . (time() - $t0) . ' s)');
      }
    }
  }
}

// ---------- 3. website ----------
$wbF = $here . '/web_build.txt';
list($c, $wwant, $e) = raw('website', 'WEB_BUILD.txt');
$wwant = trim($wwant);
$whave = is_file($wbF) ? trim(@file_get_contents($wbF)) : '';
if ($c == 404) echo "website: chưa có nhánh website\n";
elseif ($c != 200 || $wwant === '' || strlen($wwant) > 120) say("LỖI đọc WEB_BUILD.txt ($c $e)");
elseif ($whave === $wwant) echo "website đã mới nhất: $whave\n";
elseif (!$setupOk) say('website: chờ bộ cài (SETUP.json) xong mới chép — lượt sau');
elseif ($top = fetch_branch('website')) {
  $got = is_file($top . '/WEB_BUILD.txt') ? trim(file_get_contents($top . '/WEB_BUILD.txt')) : '';
  if (!is_file($top . '/index.html')) say('LỖI zip website thiếu index.html');
  elseif ($got !== $wwant) say("chờ: zip website còn bản $got, WEB_BUILD.txt đã là $wwant — lượt sau");
  else {
    $n = 0; $bad = 0; $len = strlen($top) + 1;
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($top, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $f) {
      if (!$f->isFile()) continue;
      $rel = str_replace('\\', '/', substr($f->getPathname(), $len));
      $okf = $rel === 'robots.txt' || $rel === 'sitemap.xml' || preg_match('#^[^/]+\.pdf$#', $rel) || preg_match('#^assets/[A-Za-z0-9._/ -]+$#', $rel);
      if (!$okf || strpos($rel, '..') !== false) continue;                           // index.html chép sau cùng; .htaccess / api / app / _mbtd không bao giờ
      $dst = $root . '/' . $rel;
      if (!is_dir(dirname($dst))) @mkdir(dirname($dst), 0755, true);
      if (is_file($dst) && filesize($dst) === $f->getSize() && md5_file($dst) === md5_file($f->getPathname())) continue;
      if (@copy($f->getPathname(), $dst)) $n++; else $bad++;
    }
    if ($bad == 0) {
      $src = $top . '/index.html';
      if (!(is_file($root . '/index.html') && md5_file($root . '/index.html') === md5_file($src))) { if (@copy($src, $root . '/index.html')) $n++; else $bad++; }
    }
    if ($bad == 0) { @file_put_contents($wbF, $wwant . "\n"); say('ĐÃ CẬP NHẬT website: ' . ($whave === '' ? '(lần đầu)' : $whave) . " → $wwant ($n file)"); }
    else say("LỖI chép website: $bad file không chép được ($n đã chép) — lượt sau thử lại");
  }
  rrm($here . '/x');
}
@file_put_contents($stateF, json_encode($state));
