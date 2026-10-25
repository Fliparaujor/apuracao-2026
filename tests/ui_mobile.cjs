// Teste de interface mobile (Samsung Galaxy S23: 360×780 CSS px, DPR 3) com Playwright.
// Uso: node tests/ui_mobile.cjs http://127.0.0.1:8099 [pasta_de_capturas]
const { chromium } = require("playwright");
const fs = require("node:fs");

(async () => {
const base = process.argv[2] || "http://127.0.0.1:8080";
const pasta = process.argv[3] || "";
const falhas = [];
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 360, height: 780 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
  userAgent: "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36" });
const page = await ctx.newPage();
const erros = [];
page.on("pageerror", (e) => erros.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") erros.push("console: " + m.text()); });
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.waitForSelector("#aba-painel .card", { timeout: 15000 });
const abas = ["painel", "estados", "historico", "analista", "conselho", "sistema"];
for (const aba of abas) {
  const btn = page.locator(`.rodape [data-aba="${aba}"]`);
  const box = await btn.boundingBox();
  if (!box || box.y + box.height > 780 + 1 || box.width < 40) falhas.push(`botão da aba ${aba} fora da tela ou pequeno: ${JSON.stringify(box)}`);
  await btn.click();
  await page.waitForTimeout(aba === "sistema" ? 1500 : 800);
  const metrica = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth, ativa: document.querySelector(".aba.ativa")?.id,
    cards: document.querySelectorAll(".aba.ativa .card").length }));
  if (metrica.sw > metrica.iw) falhas.push(`transbordamento horizontal na aba ${aba}: ${metrica.sw} > ${metrica.iw}`);
  if (metrica.ativa !== "aba-" + aba) falhas.push(`aba ${aba} não ficou ativa (${metrica.ativa})`);
  if (metrica.cards < 1) falhas.push(`aba ${aba} sem cartões renderizados`);
  if (pasta) { fs.mkdirSync(pasta, { recursive: true }); await page.screenshot({ path: `${pasta}/${aba}.png`, fullPage: true }); }
}
// Sistema → Testar tudo
await page.click("#sis-testar");
await page.waitForFunction(() => document.querySelector("#sis-diag .item"), null, { timeout: 60000 });
const diag = await page.evaluate(() => document.querySelector("#sis-diag").innerText);
if (!/TSE/.test(diag)) falhas.push("diagnóstico sem linha do TSE");
if (/gsk_|AIza|sk-or-v1|hf_[A-Za-z0-9]{20}/.test(diag)) falhas.push("diagnóstico expôs um segredo");
if (pasta) await page.screenshot({ path: `${pasta}/sistema-diagnostico.png`, fullPage: true });
// Analista → só matemática
await page.click('.rodape [data-aba="analista"]');
await page.fill("#an-pergunta", "O que mudou desde a última parcial?");
await page.click("#an-mat");
await page.waitForFunction(() => document.querySelector("#an-saida .item"), null, { timeout: 30000 });
const an = await page.evaluate(() => document.querySelector("#an-saida").innerText);
if (!/matemática/i.test(an)) falhas.push("analista sem leitura matemática");
if (pasta) await page.screenshot({ path: `${pasta}/analista-resposta.png`, fullPage: true });
// Conselho → status carregado
await page.click('.rodape [data-aba="conselho"]');
await page.waitForFunction(() => document.querySelector("#co-prontos") && document.querySelector("#co-prontos").textContent !== "—", null, { timeout: 15000 });
// Painel → cenário
await page.click('.rodape [data-aba="painel"]');
const temCenario = await page.locator("#cen-n").count();
if (temCenario) { await page.fill("#cen-n", "5000000"); await page.click("#cen-btn"); await page.waitForFunction(() => document.querySelector("#cen-out .item, #cen-out span"), null, { timeout: 15000 }); }
const vivo = await page.evaluate(() => document.querySelector("#pill-vivo").textContent);
console.log("Selo de atualidade:", vivo);
if (pasta) await page.screenshot({ path: `${pasta}/painel-final.png`, fullPage: true });
await browser.close();
for (const e of erros) falhas.push(e);
if (falhas.length) { console.error("FALHAS UI:\n- " + falhas.join("\n- ")); process.exit(1); }
console.log("UI mobile OK — 6 abas, sem transbordamento, sem erros de console, segredos ausentes.");

})().catch((e) => { console.error(e); process.exit(1); });
