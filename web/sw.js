/* Service worker do Radar 2026 — cache versionado SOMENTE dos arquivos do app.
   Respostas da API (/api/) nunca são cacheadas: números eleitorais antigos
   jamais podem ser apresentados como atuais. */
const VERSAO = "radar-2026-v3.0.0";
const ARQUIVOS = ["/", "/index.html", "/app.css", "/app.js", "/manifest.webmanifest",
  "/icones/icone.svg", "/icones/icone-192.png", "/icones/icone-512.png", "/icones/icone-maskable-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSAO).then((c) => c.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSAO).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("message", (e) => { if (e.data === "atualizar") self.skipWaiting(); });
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // rede sempre; sem cache
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok) { const copia = r.clone(); caches.open(VERSAO).then((c) => c.put(e.request, copia)); }
      return r;
    }).catch(() => caches.match(e.request).then((r) => r || (e.request.mode === "navigate" ? caches.match("/index.html") : undefined)))
  );
});
