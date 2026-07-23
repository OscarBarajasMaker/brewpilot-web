// BrewPilot service worker.
// Network first, on purpose: editing index.html and re-uploading must reach users
// on their next load. The cache is only a fallback for when they are offline.
// Chrome also requires a real fetch handler before it will offer to install.

// Cache name carries the build stamp, injected by update.ps1. It used to be a
// fixed 'brewpilot-v1', so the activate handler's cleanup could never fire:
// every build reused the same cache and old entries lived forever. Network
// first meant they were only served offline, so this was survivable rather than
// visible, which is the worst kind of bug. A new build now gets a new cache and
// the old one is deleted on activate.
// The version now rides in on the registration URL: index.html registers
// sw.js?v=<BUILD>, so the cache name is DERIVED, never stamped. update.ps1 used
// to rewrite this line, which meant a publish that skipped update.ps1 (a phone
// upload through Working Copy, say) left the cache name frozen at whatever the
// last PC publish wrote. That is exactly how the live sw.js ended up on
// brewpilot-2026-07-22-0718-df3100 while index.html was 12a3b2. No script has to
// touch this file any more, so no route can get it wrong.
var SWV = '';
try { SWV = new URL(self.location.href).searchParams.get('v') || ''; } catch (e) {}
var CACHE = 'brewpilot-' + (SWV || 'dev');

self.addEventListener('install', function (e) {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; })
                            .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  var url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;   // never touch the Apps Script calls

  e.respondWith(
    fetch(e.request).then(function (res) {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
      return res;
    }).catch(function () {
      return caches.match(e.request).then(function (hit) {
        return hit || caches.match('./index.html');
      });
    })
  );
});
