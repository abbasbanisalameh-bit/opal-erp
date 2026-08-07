const CACHE_NAME = 'opal-learning-r20-public-shell-v2';
const PUBLIC_SHELL = [
  '/learning/',
  '/static/learning_platform/css/platform.css',
  '/static/learning_platform/js/platform.js',
  '/static/learning_platform/icons/opal-learning-icon.svg',
  '/static/learning_platform/icons/icon-192.png',
  '/static/learning_platform/icons/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PUBLIC_SHELL)).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  const isLearningStatic = url.pathname.startsWith('/static/learning_platform/');
  if (isLearningStatic) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        }
        return response;
      }))
    );
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request, {cache: 'no-store'}).catch(() => caches.match('/learning/'))
    );
  }
});
