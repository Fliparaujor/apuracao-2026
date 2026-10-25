/* Radar 2026 — interface mobile-first. Vanilla JS, sem dependências.
   Todo número vem da API local; nada é inventado no navegador. */
(() => {
"use strict";
const $ = (id) => document.getElementById(id);
const fmtInt = (n) => Number(n || 0).toLocaleString("pt-BR");
const fmtPct = (n, d = 2) => Number(n || 0).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const titulo = (s) => { s = String(s || ""); return s === s.toUpperCase() ? s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()) : s; };
const corCand = (c) => (c && c.numero === "13" ? "c13" : c && c.numero === "22" ? "c22" : "cx");
const bgCand = (c) => (c && c.numero === "13" ? "bg13" : c && c.numero === "22" ? "bg22" : "bgx");
const guardar = (k, v) => { try { localStorage.setItem("radar3:" + k, JSON.stringify(v)); } catch (e) { /* sem espaço */ } };
const ler = (k, padrao) => { try { const v = localStorage.getItem("radar3:" + k); return v == null ? padrao : JSON.parse(v); } catch (e) { return padrao; } };
const horaLocal = (iso) => { try { return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };

const estado = {
  escopo: ler("escopo", "br"), cargo: ler("cargo", "presidente"), aba: ler("aba", "painel"),
  sessao: ler("sessao", null) || (Math.random().toString(36).slice(2, 12) + Date.now().toString(36)),
  geral: null, resultado: null, estados: null, governadores: null, historico: null, analise: null,
  provedores: null, conselhoStatus: null, reuniao: null, reuniaoId: null, offline: false, carregando: false,
  proximo: 0, ultimaConsulta: 0, ufsGov: [], muni: {},
};
guardar("sessao", estado.sessao);
const INTERVALO = 30000;
let toastTimer = null;
function toast(msg, ms = 3200) { const t = $("toast"); t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, ms); }

async function api(caminho, opcoes = {}, timeout = 25000) {
  const ctl = new AbortController(); const tm = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(caminho, { cache: "no-store", signal: ctl.signal, ...opcoes });
    const dados = await r.json().catch(() => ({ erro: "Resposta inválida do servidor." }));
    if (!r.ok) { const e = new Error(dados.erro || ("HTTP " + r.status)); e.status = r.status; e.dados = dados; throw e; }
    setOffline(false);
    return dados;
  } catch (e) {
    if (e.name === "AbortError") { const x = new Error("O servidor local demorou para responder."); x.status = 0; throw x; }
    if (e.status == null) setOffline(true);
    throw e;
  } finally { clearTimeout(tm); }
}
const post = (caminho, corpo, timeout) => api(caminho, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) }, timeout);
function setOffline(v) { if (estado.offline === v) return; estado.offline = v; $("faixa-offline").hidden = !v; if (v) $("pill-vivo").className = "pill vermelho", $("pill-vivo").textContent = "Servidor inacessível"; }

/* ------------------------------------------------------------ topo */
const ESPECIAIS = [["br", "Brasil — total nacional"], ["ce", "Ceará"], ["ap", "Amapá"], ["ce13897", "Fortaleza"], ["ap06050", "Macapá"]];
function montarEscopos() {
  const sel = $("sel-escopo"); const ufs = (estado.geral && estado.geral.ufs) || {};
  const outros = Object.entries(ufs).filter(([k]) => k.length === 2 && !["br", "zz", "ce", "ap"].includes(k)).sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));
  const extras = Object.entries(estado.muni).filter(([k]) => !ESPECIAIS.some((e) => e[0] === k));
  sel.innerHTML = '<optgroup label="Acessos rápidos">' + ESPECIAIS.map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("") + "</optgroup>" +
    (extras.length ? '<optgroup label="Municípios">' + extras.map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("") + "</optgroup>" : "") +
    '<optgroup label="Estados">' + outros.map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("") + "</optgroup>";
  sel.value = estado.escopo; if (sel.value !== estado.escopo) { estado.escopo = "br"; sel.value = "br"; }
  const cargoSel = $("sel-cargo"); const uf = estado.escopo.slice(0, 2);
  const temGov = estado.escopo.length === 2 && estado.ufsGov.includes(uf);
  cargoSel.hidden = !temGov; if (!temGov && estado.cargo !== "presidente") { estado.cargo = "presidente"; guardar("cargo", estado.cargo); }
  cargoSel.value = estado.cargo;
}
function pintarVivo(atual, d) {
  const p = $("pill-vivo"); if (estado.offline) return;
  if (!atual || !d) { p.className = "pill cinza"; p.textContent = "Sem dados do TSE"; return; }
  const cls = { ao_vivo: "vivo", estavel: "amarelo", encerrada: "azul", historica: "cinza", indefinida: "cinza" }[atual.estado] || "cinza";
  p.className = "pill " + cls; p.textContent = atual.rotulo;
}
function pintarFonte() {
  const r = estado.resultado;
  if (!r || !r.ok) { $("txt-fonte").textContent = r && r.erro ? "TSE: " + r.erro : "TSE: sem boletim para esta região"; return; }
  $("txt-fonte").textContent = "TSE " + r.horario_tse + " · " + (r.origem === "banco_local" ? "último guardado" : "boletim oficial");
}
function contagem() {
  const s = Math.max(0, Math.ceil((estado.proximo - Date.now()) / 1000));
  $("txt-prox").textContent = estado.carregando ? "atualizando…" : (estado.proximo ? "próxima em " + s + " s" : "");
}

/* ------------------------------------------------------------ carga */
async function carregarGeral() {
  try {
    estado.geral = await api("/api/estado"); guardar("geral", { t: Date.now(), d: estado.geral });
    if (!estado.ufsGov.length) { try { estado.governadores = await api("/api/governadores"); estado.ufsGov = estado.governadores.ufs || []; } catch (e) { /* opcional */ } }
    montarEscopos();
  } catch (e) {
    const g = ler("geral", null); if (g) { estado.geral = g.d; montarEscopos(); }
  }
}
async function carregarResultado(agora = false) {
  const chave = "res:" + estado.escopo + ":" + estado.cargo;
  try {
    estado.resultado = await api(`/api/resultado?escopo=${estado.escopo}&cargo=${estado.cargo}${agora ? "&agora=1" : ""}`, {}, 30000);
    guardar(chave, { t: Date.now(), d: estado.resultado });
  } catch (e) {
    const g = ler(chave, null);
    estado.resultado = g ? { ...g.d, origem: "navegador", guardado_em: g.t, atualidade: { estado: "historica", rotulo: "Guardado " + horaLocal(g.t), ao_vivo: false } } : { ok: false, erro: e.message };
  }
  pintarVivo(estado.resultado && estado.resultado.atualidade, estado.resultado && estado.resultado.ok);
  pintarFonte();
}
async function atualizar(forcar = false) {
  if (estado.carregando) return; estado.carregando = true; $("btn-atualizar").classList.add("girando"); contagem();
  try {
    await Promise.all([carregarGeral(), carregarResultado(forcar)]);
    renderPainel();
    if (estado.aba === "estados") await carregarEstados();
    if (estado.aba === "historico") await carregarHistorico();
    estado.ultimaConsulta = Date.now();
  } finally {
    estado.carregando = false; $("btn-atualizar").classList.remove("girando"); estado.proximo = Date.now() + INTERVALO; contagem();
  }
}

/* ------------------------------------------------------------ painel */
function duelo(d) {
  const c = d.candidatos || []; const a = c[0], b = c[1];
  if (!d.ok || !a || !d.votos_validos) return `<div class="vazio">${esc(d.mensagem || "Nenhum voto divulgado ainda para esta abrangência. O TSE publica as parciais a partir das 17h (Brasília). Nenhum número é inventado.")}</div>`;
  const pa = Number(a.percentual || 0), pb = b ? Number(b.percentual || 0) : 0;
  return `<div class="duelo"><div class="lado"><div class="nome">${esc(titulo(a.nome))} · ${esc(a.partido)} ${esc(a.numero)}</div><div class="pct ${corCand(a)}">${fmtPct(pa)}%</div><div class="votos">${fmtInt(a.votos)} votos</div></div><span class="vs">VS</span><div class="lado dir"><div class="nome">${b ? esc(titulo(b.nome)) + " · " + esc(b.partido) + " " + esc(b.numero) : "—"}</div><div class="pct ${corCand(b)}">${fmtPct(pb)}%</div><div class="votos">${fmtInt(b ? b.votos : 0)} votos</div></div></div>` +
    `<div class="barra"><i class="${bgCand(a)}" style="width:${Math.min(100, pa)}%"></i><i class="${bgCand(b)}" style="width:${Math.min(100, pb)}%"></i></div>` +
    `<div class="legenda"><span>${a.situacao ? "TSE: " + esc(a.situacao) : "lidera a parcial"}</span><span>Δ ${fmtInt(Math.abs(d.diferenca_votos || 0))} votos · ${fmtPct(Math.abs(d.diferenca_pp || 0))} pp</span></div>`;
}
function metricas(d) {
  const m = [["Seções totalizadas", fmtPct(d.secoes_pct) + "%", fmtInt(d.secoes_totalizadas) + " de " + fmtInt(d.secoes_total)],
    ["Votos válidos", fmtInt(d.votos_validos), d.votos_validos_pct ? fmtPct(d.votos_validos_pct) + "% dos votos" : "na abrangência"],
    ["Comparecimento", fmtInt(d.comparecimento), d.eleitorado_secoes_totalizadas ? fmtPct(100 * d.comparecimento / d.eleitorado_secoes_totalizadas) + "% das seções totalizadas" : (d.abstencao ? "abstenção " + fmtInt(d.abstencao) : "aguardando")],
    ["Brancos e nulos", fmtInt((d.brancos || 0) + (d.nulos || 0)), fmtInt(d.brancos) + " brancos · " + fmtInt(d.nulos) + " nulos"]];
  return '<div class="grade2">' + m.map((x) => `<div class="metrica"><div class="k">${x[0]}</div><div class="v">${x[1]}</div><div class="s">${esc(x[2])}</div></div>`).join("") + "</div>";
}
function itens(lista, limite = 20) {
  if (!lista || !lista.length) return '<div class="vazio">Sem itens.</div>';
  return lista.slice(0, limite).map((i) => `<div class="item"><span class="tipo ${i.tipo}">${i.tipo === "calculo" ? "cálculo" : i.tipo === "hipotese" ? "hipótese" : i.tipo === "limitacao" ? "limitação" : "fato TSE"}</span><div><b>${esc(i.titulo)}</b><p>${esc(i.texto)}</p></div></div>`).join("");
}
function renderPainel() {
  const d = estado.resultado; const el = $("aba-painel");
  if (!d) { el.innerHTML = '<div class="card"><div class="vazio">Carregando…</div></div>'; return; }
  const nome = d.nome_escopo || estado.escopo.toUpperCase();
  const cargoNome = d.cargo_nome || (estado.cargo === "governador" ? "Governador" : "Presidente");
  let html = `<div class="card"><div class="card-cab"><h2>${esc(cargoNome)} · ${esc(nome)}</h2><small>${d.ok ? esc(d.status_oficial || "") : ""}</small></div>${duelo(d)}` +
    (d.ok ? `<div class="progresso"><i style="width:${Math.min(100, d.secoes_pct || 0)}%"></i></div><div class="legenda" style="margin-top:4px"><span>boletim ${esc(d.horario_tse)}</span><span>${fmtPct(d.secoes_pct)}% das seções</span></div>` : "") +
    (d.aviso_coleta ? `<div class="aviso">Consulta agora falhou: ${esc(d.aviso_coleta)}. Exibindo o último boletim guardado.</div>` : "") +
    (d.origem === "navegador" ? `<div class="aviso">Dados guardados neste navegador às ${horaLocal(d.guardado_em)} — não são ao vivo.</div>` : "") + "</div>";
  if (d.ok) {
    html += `<div class="card"><div class="card-cab"><h2>Indicadores oficiais</h2><small>fonte: TSE</small></div>${metricas(d)}</div>`;
    html += `<div class="card"><div class="card-cab"><h2>Leitura matemática</h2><small>sem IA · reproduzível</small></div>${itens([...(d.diferencas || []), ...(d.variacao || [])])}</div>`;
    html += `<div class="card"><div class="card-cab"><h2>Cenário hipotético</h2><small>premissa explícita, sem probabilidade</small></div><p class="peq muted" style="margin:0 0 8px">Se entrarem <b>N</b> novos votos válidos, que fração deles quem está atrás precisaria para empatar? Não é previsão de quantos votos faltam.</p><div class="linha"><input id="cen-n" type="number" inputmode="numeric" min="1000" step="1000" placeholder="novos votos válidos (ex.: 5000000)" style="flex:1"><button id="cen-btn" class="btn">Calcular</button></div><div id="cen-out" class="peq" style="margin-top:8px"></div></div>`;
    html += `<div class="card"><div class="card-cab"><h2>Fonte oficial</h2></div><div class="peq muted" style="overflow-wrap:anywhere">${esc(d.fonte)}<br>Consulta ${esc(d.consulta_utc)} UTC · ${esc((d.atualidade || {}).rotulo || "")}. Percentual de seções ≠ percentual de votos restantes.</div></div>`;
  }
  const gov = estado.governadores;
  if (gov && gov.disputas && gov.disputas.length && estado.cargo === "presidente" && estado.escopo === "br") {
    html += `<div class="card"><div class="card-cab"><h2>Governadores · 2º turno</h2><small>${gov.verificado_no_tse ? "UFs confirmadas no TSE" : "lista padrão (não verificada)"}</small></div>` +
      gov.disputas.map((g) => { const a = g.candidatos && g.candidatos[0], b = g.candidatos && g.candidatos[1]; return `<button class="uf" data-gov="${g.escopo}"><div><div class="nm">${esc(g.nome_escopo)}</div><div class="sb">${g.ok && a && g.votos_validos ? esc(titulo(a.nome)) + " lidera · " + fmtPct(g.secoes_pct, 1) + "% seções" : esc(g.mensagem || "aguardando votos")}</div></div><div class="val">${g.ok && a && g.votos_validos ? fmtPct(a.percentual) + "%" : "—"}<small>${a ? esc(titulo(a.nome)).slice(0, 14) : ""}</small></div><div class="val">${g.ok && b && g.votos_validos ? fmtPct(b.percentual) + "%" : "—"}<small>${b ? esc(titulo(b.nome)).slice(0, 14) : ""}</small></div></button>`; }).join("") +
      (gov.sem_arquivo && gov.sem_arquivo.length ? `<p class="mini dim" style="margin:8px 0 0">Sem arquivo no TSE: ${gov.sem_arquivo.map((x) => x.uf.toUpperCase()).join(", ")}.</p>` : "") + "</div>";
  }
  el.innerHTML = html;
  const cb = $("cen-btn"); if (cb) cb.addEventListener("click", calcularCenario);
  el.querySelectorAll("[data-gov]").forEach((b) => b.addEventListener("click", () => { estado.escopo = b.dataset.gov; estado.cargo = "governador"; guardar("escopo", estado.escopo); guardar("cargo", estado.cargo); montarEscopos(); carregarResultado().then(renderPainel); }));
}
async function calcularCenario() {
  const n = Number($("cen-n").value); const out = $("cen-out");
  if (!n || n < 1000) { out.innerHTML = '<span class="muted">Informe um número de votos (mínimo 1.000).</span>'; return; }
  out.innerHTML = '<span class="spin"></span>';
  try {
    const r = await post("/api/cenario", { escopo: estado.escopo, cargo: estado.cargo, premissas: { novos_votos_validos: [n] } });
    const c = r.cenarios && r.cenarios[0];
    out.innerHTML = !r.ok ? esc(r.motivo) : `<div class="item"><span class="tipo hipotese">hipótese</span><div><b>${fmtInt(n)} novos votos válidos</b><p>${c.pct_necessario_para_quem_esta_atras_empatar == null ? "Impossível empatar com esse número de votos: a diferença atual (" + fmtInt(r.diferenca_votos) + ") é maior que N." : esc(r.segundo) + " precisaria de mais de " + fmtPct(c.pct_necessario_para_quem_esta_atras_empatar) + "% desses votos para empatar com " + esc(r.lider) + " (diferença atual " + fmtInt(r.diferenca_votos) + " votos)."}</p><p class="mini dim">${esc((r.avisos || []).join(" "))}</p></div></div>`;
  } catch (e) { out.innerHTML = `<span class="muted">${esc(e.message)}</span>`; }
}

/* ------------------------------------------------------------ estados */
let ordem = ler("ordem", "nome");
async function carregarEstados() {
  try { estado.estados = await api("/api/estados", {}, 30000); } catch (e) { if (!estado.estados) estado.estados = { estados: [], regional: [], erro: e.message }; }
  renderEstados();
}
function renderEstados() {
  const el = $("aba-estados"); const d = estado.estados;
  if (!d) { el.innerHTML = '<div class="card"><div class="vazio">Carregando…</div></div>'; return; }
  let lista = [...(d.estados || [])];
  const margem = (x) => (x.ok && x.candidatos && x.candidatos.length > 1 ? Math.abs(x.candidatos[0].percentual - x.candidatos[1].percentual) : -1);
  if (ordem === "nome") lista.sort((a, b) => a.nome_escopo.localeCompare(b.nome_escopo, "pt-BR"));
  if (ordem === "secoes") lista.sort((a, b) => (b.secoes_pct || 0) - (a.secoes_pct || 0));
  if (ordem === "margem") lista.sort((a, b) => margem(a) - margem(b));
  const com = lista.filter((x) => x.ok && x.votos_validos).length;
  el.innerHTML = `<div class="card"><div class="card-cab"><h2>Presidente por UF</h2><small>${com} de 27 com votos</small></div>` +
    `<div class="chips">${[["nome", "A–Z"], ["secoes", "Mais apurado"], ["margem", "Menor margem"]].map(([k, v]) => `<button class="chip ${ordem === k ? "ativo" : ""}" data-ordem="${k}">${v}</button>`).join("")}</div>` +
    lista.map((x) => { const a = x.candidatos && x.candidatos[0], b = x.candidatos && x.candidatos[1]; const v = x.ok && x.votos_validos && a; const p13 = v ? (x.candidatos.find((c) => c.numero === "13") || {}).percentual || 0 : 0; const p22 = v ? (x.candidatos.find((c) => c.numero === "22") || {}).percentual || 0 : 0;
      return `<button class="uf" data-uf="${x.escopo}"><div><div class="nm">${esc(x.nome_escopo)}</div><div class="sb">${v ? esc(titulo(a.nome)) + " lidera · " + esc(x.horario_tse || "") : "Aguardando votos"}</div></div><div class="val">${fmtPct(x.secoes_pct || 0, 1)}%<small>seções</small></div><div class="val"><span class="${v ? corCand(a) : ""}">${v ? "+" + fmtPct(a.percentual - (b ? b.percentual : 0)) + " pp" : "—"}</span><small>vantagem</small><div class="mini-barra"><i class="bg13" style="width:${p13}%"></i><i class="bg22" style="width:${p22}%"></i></div></div></button>`; }).join("") + "</div>" +
    `<div class="card"><div class="card-cab"><h2>Variação regional</h2><small>cálculo sem IA</small></div>${itens(d.regional || [])}${d.erro ? `<div class="erro">${esc(d.erro)}</div>` : ""}</div>`;
  el.querySelectorAll("[data-ordem]").forEach((b) => b.addEventListener("click", () => { ordem = b.dataset.ordem; guardar("ordem", ordem); renderEstados(); }));
  el.querySelectorAll("[data-uf]").forEach((b) => b.addEventListener("click", () => { estado.escopo = b.dataset.uf; estado.cargo = "presidente"; guardar("escopo", estado.escopo); guardar("cargo", estado.cargo); montarEscopos(); mudarAba("painel"); carregarResultado().then(renderPainel); }));
}

/* ------------------------------------------------------------ histórico */
async function carregarHistorico() {
  try { estado.historico = await api(`/api/historico?escopo=${estado.escopo}&cargo=${estado.cargo}&limite=300`); } catch (e) { estado.historico = { erro: e.message, evolucao: { pontos: [] } }; }
  renderHistorico();
}
function grafico(pontos) {
  if (!pontos || pontos.length < 2) return '<div class="vazio">São necessários dois boletins diferentes guardados no servidor para traçar a evolução.</div>';
  const w = 640, h = 240, pad = { l: 40, r: 40, t: 14, b: 30 }, iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const nums = [...new Set(pontos.flatMap((p) => p.candidatos.map((c) => c.numero)))].slice(0, 3);
  const x = (i) => pad.l + (i / (pontos.length - 1)) * iw;
  const y = (v) => pad.t + ((100 - v) / 100) * ih;
  const cores = { "13": "#ef4d5b", "22": "#4a90ff" };
  let g = "";
  for (const v of [0, 25, 50, 75, 100]) g += `<line x1="${pad.l}" y1="${y(v)}" x2="${w - pad.r}" y2="${y(v)}" stroke="#22324a" stroke-dasharray="3 5"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end" fill="#607690" font-size="11">${v}%</text>`;
  const linhas = nums.map((n) => `<path d="${pontos.map((p, i) => { const c = p.candidatos.find((z) => z.numero === n); return (i ? "L" : "M") + x(i).toFixed(1) + " " + y(c ? c.percentual : 0).toFixed(1); }).join(" ")}" fill="none" stroke="${cores[n] || "#f5b84a"}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`).join("");
  const sec = `<path d="${pontos.map((p, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(p.secoes_pct || 0).toFixed(1)).join(" ")}" fill="none" stroke="#4cc9f0" stroke-width="1.5" stroke-dasharray="4 4"/>`;
  const ini = pontos[0].horario_tse || "", fim = pontos[pontos.length - 1].horario_tse || "";
  return `<svg class="grafico" viewBox="0 0 ${w} ${h}" role="img" aria-label="Evolução dos percentuais por boletim">${g}${sec}${linhas}<text x="${pad.l}" y="${h - 8}" fill="#607690" font-size="11">${esc(ini.slice(11, 16))}</text><text x="${w - pad.r}" y="${h - 8}" text-anchor="end" fill="#607690" font-size="11">${esc(fim.slice(11, 16))}</text></svg>` +
    `<div class="legenda" style="margin-top:4px">${nums.map((n) => `<span style="color:${cores[n] || "#f5b84a"}">● ${esc(n)}</span>`).join(" ")}<span style="color:#4cc9f0">- - seções totalizadas</span></div>`;
}
function renderHistorico() {
  const el = $("aba-historico"); const d = estado.historico;
  if (!d) { el.innerHTML = '<div class="card"><div class="vazio">Carregando…</div></div>'; return; }
  const pts = (d.evolucao && d.evolucao.pontos) || []; const cont = (d.contadores && d.contadores[0]) || {};
  const trocas = (d.evolucao && d.evolucao.trocas_de_lideranca) || [];
  el.innerHTML = `<div class="card"><div class="card-cab"><h2>Evolução · ${esc((estado.resultado && estado.resultado.nome_escopo) || estado.escopo)}</h2><small>${pts.length} boletins guardados</small></div>${grafico(pts)}` +
    (trocas.length ? `<div class="aviso">${trocas.length} troca(s) de liderança registrada(s): ${trocas.map((t) => esc(t.horario_tse) + " " + t.de + "→" + t.para).join("; ")}</div>` : "") + "</div>" +
    `<div class="card"><div class="card-cab"><h2>Consultas × boletins novos</h2><small>distinção honesta</small></div><div class="grade3"><div class="metrica"><div class="k">Consultas</div><div class="v">${fmtInt(cont.consultas)}</div><div class="s">ao TSE, esta região</div></div><div class="metrica"><div class="k">Boletins novos</div><div class="v">${fmtInt(cont.boletins_novos)}</div><div class="s">dados diferentes</div></div><div class="metrica"><div class="k">Repetidos</div><div class="v">${fmtInt(cont.repetidos)}</div><div class="s">mesmo boletim</div></div></div><p class="mini dim" style="margin:8px 0 0">Uma resposta HTTP 200 do TSE não significa boletim novo: só gravamos quando os números mudam. Último boletim novo: ${cont.ultimo_boletim_utc ? horaLocal(cont.ultimo_boletim_utc) : "—"}.</p></div>` +
    `<div class="card"><div class="card-cab"><h2>Boletins</h2></div><div class="rolagem"><table class="tabela"><thead><tr><th>TSE</th><th>Seções</th><th>Válidos</th>${(pts[0] ? pts[0].candidatos : []).slice(0, 3).map((c) => `<th>${esc(c.numero)}</th>`).join("")}</tr></thead><tbody>` +
    [...pts].reverse().slice(0, 60).map((p) => `<tr><td>${esc((p.horario_tse || "").slice(11))}</td><td>${fmtPct(p.secoes_pct)}%</td><td>${fmtInt(p.votos_validos)}</td>${p.candidatos.slice(0, 3).map((c) => `<td>${fmtPct(c.percentual)}%</td>`).join("")}</tr>`).join("") +
    `</tbody></table></div>${d.erro ? `<div class="erro">${esc(d.erro)}</div>` : ""}</div>`;
}

/* ------------------------------------------------------------ analista */
const PERGUNTAS = ["O que mudou desde a última parcial?", "Quais diferenças regionais estão aparecendo?", "O comportamento da apuração no Ceará difere do Amapá?",
  "Como comparar esta parcial com o primeiro turno?", "Quais hipóteses poderiam explicar essa mudança?", "Que dados ainda não temos?", "Mostre os cálculos usados."];
function renderAnalista() {
  const el = $("aba-analista"); if (el.dataset.pronto) { return; } el.dataset.pronto = "1";
  el.innerHTML = `<div class="card"><div class="card-cab"><h2>✦ Analista</h2><small>1 modelo + matemática</small></div><p class="peq muted" style="margin:0 0 8px">Pergunte livremente. A resposta da IA vem sempre acompanhada da leitura matemática, que funciona mesmo sem nenhuma chave.</p>` +
    `<div class="chips">${PERGUNTAS.map((p) => `<button class="chip" data-p="${esc(p)}">${esc(p)}</button>`).join("")}</div>` +
    `<textarea id="an-pergunta" maxlength="600" placeholder="Sua pergunta sobre a apuração…"></textarea><div class="acoes"><button id="an-ia" class="btn primario">Perguntar à IA</button><button id="an-mat" class="btn">Só matemática</button></div><div id="an-status" class="mini dim" style="margin-top:6px"></div></div>` +
    `<div id="an-saida"></div><div class="card"><div class="card-cab"><h2>Histórico de perguntas</h2></div><div id="an-hist" class="peq muted">—</div></div>`;
  el.querySelectorAll("[data-p]").forEach((b) => b.addEventListener("click", () => { $("an-pergunta").value = b.dataset.p; }));
  $("an-ia").addEventListener("click", () => perguntar(false)); $("an-mat").addEventListener("click", () => perguntar(true));
  carregarHistAnalista();
}
async function carregarHistAnalista() {
  try { const h = await api(`/api/analista/historico?sessao=${estado.sessao}&limite=10`); const box = $("an-hist"); if (!box) return;
    box.innerHTML = h.conversas.length ? h.conversas.map((c) => `<div class="item"><span class="tipo ${c.provedor ? "calculo" : "limitacao"}">${c.provedor ? "IA" : "sem IA"}</span><div><b>${esc(c.pergunta)}</b><p>${esc(c.escopo.toUpperCase())} · ${esc(c.horario_tse || "")} · ${c.provedor ? esc(c.provedor) + " · " + esc(c.modelo) : "motor matemático"}<br>${esc(c.resumo)}</p></div></div>`).join("") : "Nenhuma pergunta nesta sessão.";
  } catch (e) { /* silencioso */ }
}
function auditoriaHtml(a) {
  if (!a) return "";
  const ns = (a.nao_suportados || []).map((x) => x.citado).join(", ");
  return `<div class="${a.nao_suportados && a.nao_suportados.length ? "aviso" : "ok-box"}">Auditoria numérica automática: ${esc(a.veredito)} · ${a.confirmados}/${a.total} números localizados na evidência${ns ? " · sem suporte: " + esc(ns) : ""}${a.alertas && a.alertas.length ? " · alertas: " + esc(a.alertas.join(", ")) : ""}</div>`;
}
async function perguntar(semIa) {
  const btn = $("an-ia"), btn2 = $("an-mat"); btn.disabled = btn2.disabled = true;
  $("an-status").innerHTML = '<span class="spin"></span> ' + (semIa ? "Calculando…" : "Consultando o TSE e o modelo disponível… (até 90 s)");
  $("an-saida").innerHTML = "";
  try {
    const r = await post("/api/analista/perguntar", { escopo: estado.escopo, cargo: estado.cargo, pergunta: $("an-pergunta").value, sessao: estado.sessao, sem_ia: semIa }, 120000);
    const ia = r.ia || {};
    let html = "";
    if (ia.ok) html += `<div class="card"><div class="card-cab"><h2>Resposta da IA</h2><small>${esc(ia.provedor_nome)} · ${esc(ia.modelo)} · ${Math.round((ia.duracao_ms || 0) / 1000)} s</small></div><div class="texto">${esc(ia.texto)}</div>${auditoriaHtml(ia.auditoria)}<p class="mini dim" style="margin:8px 0 0">${esc(ia.aviso)}</p></div>`;
    else html += `<div class="card"><div class="card-cab"><h2>Sem resposta de IA</h2></div><div class="aviso">${esc(ia.motivo || "Indisponível")}${ia.tentativas_falhas && ia.tentativas_falhas.length ? "<br>" + ia.tentativas_falhas.map((t) => esc(t.provedor + ": " + t.erro)).join("<br>") : ""}${(ia.provedores || []).map((p) => "<br>" + esc(p.id + ": " + p.mensagem)).join("")}</div></div>`;
    const m = r.matematica || {};
    html += `<div class="card"><div class="card-cab"><h2>Leitura matemática (sem IA)</h2><small>${esc(m.horario_tse || "")}</small></div>${itens(m.itens || [], 30)}</div>`;
    $("an-saida").innerHTML = html; $("an-status").textContent = "Concluído · " + esc(r.nome_escopo) + " · boletim " + esc(r.horario_tse);
    carregarHistAnalista();
  } catch (e) { $("an-status").textContent = ""; $("an-saida").innerHTML = `<div class="card"><div class="erro">Não foi possível concluir: ${esc(e.message)}. A apuração numérica continua disponível no Painel.</div></div>`; }
  finally { btn.disabled = btn2.disabled = false; }
}

/* ------------------------------------------------------------ conselho */
function renderConselhoBase() {
  const el = $("aba-conselho"); if (el.dataset.pronto) return; el.dataset.pronto = "1";
  el.innerHTML = `<div class="card"><div class="card-cab"><div><h2 style="font-size:22px;letter-spacing:-.5px;text-transform:none;color:var(--text)">◈ O Conselho</h2><div class="mini muted">Modelos independentes analisam, confrontam, replicam; uma auditoria confere os números; o relator preserva as divergências.</div></div></div>` +
    `<div class="grade3" id="co-stats"><div class="metrica"><div class="k">Prontos</div><div class="v" id="co-prontos">—</div><div class="s">modelos</div></div><div class="metrica"><div class="k">Provedores</div><div class="v" id="co-prov">—</div><div class="s">distintos</div></div><div class="metrica"><div class="k">Rodadas</div><div class="v">5</div><div class="s">máximo</div></div></div>` +
    `<div class="sec">Cadeiras</div><div id="co-cadeiras" class="grade2">—</div><div id="co-nota" class="mini dim" style="margin-top:8px"></div>` +
    `<div class="sec">Pergunta ao Conselho</div><textarea id="co-pergunta" maxlength="600" placeholder="Ex.: Quais hipóteses explicam a diferença entre Ceará e Amapá? O que observar nos próximos boletins?"></textarea>` +
    `<div class="acoes"><button id="co-convocar" class="btn primario" disabled>◈ Convocar o Conselho</button><button id="co-cancelar" class="btn perigo" hidden>Cancelar</button></div>` +
    `<label class="toggle" style="margin-top:6px"><span>Reconvocar automaticamente a cada boletim novo (a cada ≥ 10 min, só com esta aba aberta; consome cota)</span><input id="co-auto" type="checkbox"></label>` +
    `<div id="co-progresso" class="timeline" hidden></div></div>` +
    `<div id="co-saida"></div><div class="card"><div class="card-cab"><h2>Reuniões anteriores</h2></div><div id="co-hist" class="peq muted">—</div></div>`;
  $("co-convocar").addEventListener("click", convocar); $("co-cancelar").addEventListener("click", cancelarReuniao);
  $("co-auto").addEventListener("change", (e) => { estado.autoConselho = e.target.checked; });
}
async function carregarConselho() {
  renderConselhoBase();
  try { estado.conselhoStatus = await api("/api/conselho/status"); } catch (e) { $("co-nota").textContent = "Servidor indisponível: " + e.message; return; }
  const s = estado.conselhoStatus;
  $("co-prontos").textContent = s.modelos_prontos; $("co-prov").textContent = s.provedores_distintos;
  const cad = s.cadeiras.map((c) => `<div class="cadeira"><b>${esc(c.papel_nome)}</b><div class="sub">${esc(c.provedor_nome)} · ${esc(c.modelo)}</div><div class="badges"><span class="badge ok">chave</span><span class="badge ok">autenticado</span><span class="badge ok">disponível</span>${c.independente ? "" : '<span class="badge meio">mesmo provedor</span>'}${s.relator && s.relator.id === c.id ? '<span class="badge info">relator</span>' : ""}</div></div>`).join("") +
    s.nao_prontos.map((c) => `<div class="cadeira" style="opacity:.75"><b>${esc(c.provedor_nome)}</b><div class="sub">${esc(c.motivo)}</div><div class="badges"><span class="badge ${c.configurado ? "ok" : "nao"}">chave</span><span class="badge ${c.autenticado ? "ok" : "nao"}">autenticado</span><span class="badge nao">indisponível</span></div></div>`).join("");
  $("co-cadeiras").innerHTML = cad || '<div class="vazio">Nenhum provedor.</div>';
  const emAndamento = s.reunioes_em_andamento > 0;
  $("co-convocar").disabled = s.modelos_prontos < 1 || emAndamento;
  $("co-nota").textContent = s.modelos_prontos === 0 ? "Nenhum modelo pronto. Configure chaves gratuitas em Sistema (ou no Termux: bash radar.sh chaves) e teste a autenticação. Com 1 modelo o resultado é uma análise individual; com 2+ há confronto." : s.modelos_prontos === 1 ? "Apenas 1 modelo pronto: a reunião será classificada como análise individual (sem confronto)." : s.nota;
  carregarHistConselho();
}
async function carregarHistConselho() {
  try { const h = await api(`/api/conselho/historico?limite=10`); const box = $("co-hist"); if (!box) return;
    box.innerHTML = h.reunioes.length ? h.reunioes.map((r) => `<button class="uf" data-conv="${r.id}"><div><div class="nm">${esc(r.pergunta)}</div><div class="sb">${esc(r.escopo.toUpperCase())} · ${esc(r.horario_tse || "")} · ${esc(r.classificacao || r.status)} · ${r.modelos} modelo(s)</div></div><div class="val">${horaLocal(r.criado_utc)}<small>abrir</small></div><div></div></button>`).join("") : "Nenhuma reunião registrada.";
    box.querySelectorAll("[data-conv]").forEach((b) => b.addEventListener("click", async () => { try { const c = await api("/api/conversas/" + b.dataset.conv); renderReuniao(c.resposta); window.scrollTo({ top: 0 }); } catch (e) { toast(e.message); } }));
  } catch (e) { /* silencioso */ }
}
let pollTimer = null;
async function convocar() {
  $("co-convocar").disabled = true; $("co-cancelar").hidden = false; $("co-progresso").hidden = false; $("co-progresso").innerHTML = "<div>Enviando convocação…</div>"; $("co-saida").innerHTML = "";
  try {
    const r = await post("/api/conselho/reuniao", { escopo: estado.escopo, cargo: estado.cargo, pergunta: $("co-pergunta").value, sessao: estado.sessao });
    estado.reuniaoId = r.id; estado.ultimaReuniao = Date.now(); estado.assinaturaReuniao = estado.escopo + "|" + ((estado.resultado || {}).horario_tse || "");
    acompanhar();
  } catch (e) { $("co-progresso").innerHTML = `<div>Falha: ${esc(e.message)}</div>`; $("co-convocar").disabled = false; $("co-cancelar").hidden = true; }
}
async function acompanhar() {
  clearTimeout(pollTimer);
  try {
    const j = await api("/api/conselho/reuniao/" + estado.reuniaoId);
    $("co-progresso").innerHTML = j.progresso.map((p) => `<div>${horaLocal(p.t * 1000)} · ${esc(p.mensagem)}</div>`).join("") || "<div>Aguardando…</div>";
    $("co-progresso").scrollTop = 1e6;
    if (j.parcial && j.parcial.cadeiras && j.status === "em_andamento") renderReuniao(j.parcial, true);
    if (j.status === "em_andamento") { pollTimer = setTimeout(acompanhar, 2500); return; }
    $("co-cancelar").hidden = true; $("co-convocar").disabled = false;
    if (j.status === "falha") { $("co-saida").innerHTML = `<div class="card"><div class="erro">Reunião falhou: ${esc(j.erro)}</div></div>`; }
    else renderReuniao(j.resultado || j.parcial);
    carregarHistConselho(); carregarConselho();
  } catch (e) { $("co-progresso").innerHTML += `<div>Erro ao acompanhar: ${esc(e.message)}</div>`; pollTimer = setTimeout(acompanhar, 5000); }
}
async function cancelarReuniao() { if (!estado.reuniaoId) return; try { await post("/api/conselho/cancelar", { id: estado.reuniaoId }); toast("Cancelamento solicitado."); } catch (e) { toast(e.message); } }
function rodadaHtml(c, k, rotulo) {
  const r = c[k]; if (!r) return "";
  const aud = c.auditoria && c.auditoria[k];
  return `<details><summary>${rotulo}${r.ok ? "" : ' <span class="badge nao">não participou</span>'}</summary><div class="texto">${r.ok ? esc(r.texto) : "Motivo: " + esc(r.erro || "sem resposta")}</div>${aud ? auditoriaHtml(aud) : ""}</details>`;
}
function renderReuniao(r, parcial = false) {
  if (!r) return;
  const cls = { deliberacao: ["ok-box", "Deliberação com confronto entre modelos"], analise_individual: ["aviso", "Análise individual: apenas um modelo respondeu, sem confronto"], debate_sem_relatoria: ["aviso", "Debate sem relatoria por IA: síntese automática"], somente_matematica: ["aviso", "Somente motor matemático: nenhum modelo participou"], cancelada: ["erro", "Reunião cancelada"] }[r.classificacao] || ["aviso", parcial ? "Reunião em andamento…" : esc(r.status || "")];
  const rel = r.relatorio || {};
  let html = `<div class="card"><div class="card-cab"><h2>Relatório · ${esc(r.nome_escopo || r.escopo)}</h2><small>TSE ${esc(r.horario_tse || "")} · ${(r.rodadas_executadas || []).length}/5 rodadas</small></div><div class="${cls[0]}">${cls[1]}${rel.relator ? " · Relator: " + esc(rel.relator.provedor_nome) + " · " + esc(rel.relator.modelo) + (rel.automatico ? " (falhou; síntese automática)" : "") : ""}</div>` +
    (rel.texto ? `<div class="relatorio" style="margin-top:10px">${esc(rel.texto)}</div>${auditoriaHtml(rel.auditoria)}` : (parcial ? '<div class="vazio" style="margin-top:10px"><span class="spin"></span> aguardando as rodadas…</div>' : "")) +
    (r.avisos || []).map((a) => `<p class="mini dim" style="margin:6px 0 0">• ${esc(a)}</p>`).join("") +
    `<p class="mini dim" style="margin:8px 0 0;overflow-wrap:anywhere">Fonte: ${esc(r.fonte || "")}</p></div>`;
  if (r.auditoria && r.auditoria.itens && r.auditoria.itens.length) html += `<div class="card"><div class="card-cab"><h2>Rodada 4 · auditoria determinística</h2></div><p class="peq muted" style="margin:0 0 6px">${esc(r.auditoria.resumo)}</p>${r.auditoria.itens.map((i) => `<div class="item"><span class="tipo ${i.nao_suportados.length || i.alertas.length ? "limitacao" : "fato"}">${i.nao_suportados.length || i.alertas.length ? "contestado" : "compatível"}</span><div><b>${esc(i.papel_nome)} · ${esc(i.provedor_nome)} · ${i.rodada === "rodada1" ? "parecer" : "réplica"}</b><p>${i.confirmados}/${i.total} números localizados${i.nao_suportados.length ? " · sem suporte: " + esc(i.nao_suportados.map((x) => x.citado).join(", ")) : ""}${i.alertas.length ? " · " + esc(i.alertas.join(", ")) : ""}</p></div></div>`).join("")}</div>`;
  const criticas = (r.cadeiras || []).filter((c) => c.rodada2 && c.rodada2.ok);
  if (criticas.length) html += `<div class="card"><div class="card-cab"><h2>Divergências e objeções</h2><small>rodada 2</small></div>${criticas.map((c) => `<details><summary>${esc(c.papel_nome)} · ${esc(c.provedor_nome)}</summary><div class="texto">${esc(c.rodada2.texto)}</div></details>`).join("")}</div>`;
  html += `<div class="card"><div class="card-cab"><h2>Cadeiras e pareceres</h2><small>${(r.cadeiras || []).filter((c) => c.participa).length} participaram</small></div>` +
    (r.cadeiras || []).map((c) => `<div class="cadeira" style="margin-bottom:8px"><b>${esc(c.papel_nome)}</b><div class="sub">${esc(c.provedor_nome)} · ${esc((c.rodada1 && c.rodada1.modelo_real) || c.modelo)}</div><div class="badges"><span class="badge ok">chave</span><span class="badge ok">autenticado</span><span class="badge ${c.disponivel ? "ok" : "nao"}">disponível</span><span class="badge ${c.participa ? "ok" : "nao"}">${c.participa ? "participou" : "não participou"}</span>${c.independente ? "" : '<span class="badge meio">mesmo provedor</span>'}</div>${rodadaHtml(c, "rodada1", "1 · Parecer independente")}${rodadaHtml(c, "rodada2", "2 · Objeções que fez")}${rodadaHtml(c, "rodada3", "3 · Réplica")}</div>`).join("") +
    (r.nao_prontos || []).map((c) => `<div class="cadeira" style="margin-bottom:8px;opacity:.7"><b>${esc(c.provedor_nome)}</b><div class="sub">${esc(c.motivo)}</div></div>`).join("") + "</div>";
  html += `<div class="card"><details><summary>Evidência enviada aos modelos</summary><div class="texto">${esc(r.evidencia_texto || "")}</div></details></div>`;
  $("co-saida").innerHTML = html;
}

/* ------------------------------------------------------------ sistema */
function renderSistemaBase() {
  const el = $("aba-sistema"); if (el.dataset.pronto) return; el.dataset.pronto = "1";
  el.innerHTML = `<div class="card"><div class="card-cab"><h2>⚙ Diagnóstico</h2><small id="sis-versao"></small></div><div class="acoes"><button id="sis-testar" class="btn primario">Testar tudo</button><button id="sis-copiar" class="btn">Copiar resultado</button></div><div id="sis-diag" class="peq" style="margin-top:10px"><div class="vazio">Toque em Testar tudo. As chaves nunca aparecem.</div></div></div>` +
    `<div class="card"><div class="card-cab"><h2>Provedores de IA</h2><small>gratuitos, sem cartão</small></div><div id="sis-prov">—</div><div class="sec">Como adicionar ou trocar uma chave</div><p class="peq muted" style="margin:0">No Termux, pare o servidor (Ctrl+C) e rode:</p><div class="codigo">bash radar.sh chaves</div><p class="peq muted" style="margin:0">O assistente pede cada chave sem mostrá-la, testa a autenticação e guarda em ~/.radar2026/segredos.env (permissão 600). Depois: <span class="mono">bash radar.sh iniciar</span>.</p></div>` +
    `<div class="card"><div class="card-cab"><h2>Configuração</h2></div><div id="sis-config">—</div></div>` +
    `<div class="card"><div class="card-cab"><h2>Cotas gratuitas</h2><small>últimas 24 h</small></div><div id="sis-cotas">—</div></div>` +
    `<div class="card"><div class="card-cab"><h2>Sobre</h2></div><p class="peq muted" style="margin:0">Radar 2026 + O Conselho · dados oficiais de resultados.tse.jus.br · projeto independente, sem vínculo com o TSE. Nenhuma probabilidade de vitória é calculada. Instale na tela inicial pelo menu ⋮ do Chrome → “Instalar app”. Mantenha o Termux aberto com <span class="mono">termux-wake-lock</span>; o Android pode suspender o processo em segundo plano.</p></div>`;
  $("sis-testar").addEventListener("click", testarTudo); $("sis-copiar").addEventListener("click", copiarDiag);
}
let ultimoDiag = null;
async function carregarSistema() {
  renderSistemaBase(); await carregarProvedores(); await carregarConfig(); await carregarCotas();
}
async function carregarProvedores(testar = false) {
  try { estado.provedores = await api("/api/provedores" + (testar ? "?testar=1" : ""), {}, 60000); } catch (e) { $("sis-prov").innerHTML = `<div class="erro">${esc(e.message)}</div>`; return; }
  const cor = (e) => ({ autenticado: "ok", sem_chave: "nao", chave_invalida: "nao", sem_permissao: "nao", limite: "meio", modelo_indisponivel: "meio", rede: "meio", nao_testado: "meio", pagamento: "nao", erro: "meio" }[e] || "meio");
  const rot = (e) => ({ autenticado: "autenticado", sem_chave: "sem chave", chave_invalida: "chave inválida", sem_permissao: "sem permissão", limite: "limite atingido", modelo_indisponivel: "modelo indisponível", rede: "sem rede", nao_testado: "não testado", pagamento: "exige pagamento", erro: "erro" }[e] || e);
  $("sis-prov").innerHTML = estado.provedores.provedores.map((p) => `<div class="cadeira" style="margin-bottom:8px"><div class="linha" style="justify-content:space-between"><b>${esc(p.nome)}</b><span class="badge ${p.pronto ? "ok" : "nao"}">${p.pronto ? "pronto" : "não pronto"}</span></div><div class="sub">${esc(p.mensagem)}${p.http ? " (HTTP " + p.http + ")" : ""}${p.modelo ? "<br>Modelo real: <span class='mono'>" + esc(p.modelo) + "</span>" : ""}${p.cota && p.cota.desativado ? "<br>Desativado: " + esc(p.cota.desativado) : ""}${p.cota && p.cota.cooldown_restante_s ? "<br>Pausa de " + p.cota.cooldown_restante_s + " s (" + esc(p.cota.motivo_cooldown) + ")" : ""}</div><div class="badges"><span class="badge ${p.configurado ? "ok" : "nao"}">chave: ${p.configurado ? p.origem_chave : "ausente"}</span><span class="badge ${cor(p.estado_autenticacao)}">${rot(p.estado_autenticacao)}</span><span class="badge ${p.modelo ? "ok" : "nao"}">modelo ${p.modelo ? "ok" : "—"}</span>${p.desativado_pelo_usuario ? '<span class="badge meio">desligado por você</span>' : ""}</div><div class="linha" style="margin-top:8px"><button class="chip" data-testar="${p.id}">Testar</button>${p.cota && (p.cota.desativado || p.cota.cooldown_restante_s) ? `<button class="chip" data-reativar="${p.id}">Reativar</button>` : ""}<button class="chip" data-ativar="${p.id}" data-valor="${p.desativado_pelo_usuario ? 1 : 0}">${p.desativado_pelo_usuario ? "Ligar" : "Desligar"}</button><a class="chip" href="${esc(p.link)}" target="_blank" rel="noopener">Criar chave grátis ↗</a></div><p class="mini dim" style="margin:6px 0 0">${esc(p.nota_gratuita)}</p></div>`).join("");
  $("sis-prov").querySelectorAll("[data-testar]").forEach((b) => b.addEventListener("click", async () => { b.disabled = true; try { const r = await post("/api/provedores/testar", { provedor: b.dataset.testar }, 60000); toast(r.resultado.nome + ": " + r.resultado.mensagem); } catch (e) { toast(e.message); } await carregarProvedores(); }));
  $("sis-prov").querySelectorAll("[data-reativar]").forEach((b) => b.addEventListener("click", async () => { await post("/api/provedores/reativar", { provedor: b.dataset.reativar }); await carregarProvedores(); }));
  $("sis-prov").querySelectorAll("[data-ativar]").forEach((b) => b.addEventListener("click", async () => { await post("/api/provedores/ativar", { provedor: b.dataset.ativar, ativo: b.dataset.valor === "1" }); await carregarProvedores(); }));
}
async function carregarConfig() {
  try { const r = await api("/api/config"); const c = r.config;
    $("sis-config").innerHTML = `<label class="toggle"><span>Coleta automática do TSE (a cada ${c.intervalo_coleta_segundos} s)</span><input type="checkbox" id="cf-coleta" ${c.coleta_automatica ? "checked" : ""}></label><label class="toggle"><span>Intervalo de coleta (s)</span><input type="number" id="cf-intervalo" min="15" max="600" value="${c.intervalo_coleta_segundos}"></label><label class="toggle"><span>Limite de chamadas de IA por sessão</span><input type="number" id="cf-limite" min="5" max="2000" value="${c.limites_sessao.chamadas_ia_por_sessao}"></label><label class="toggle"><span>Reuniões do Conselho por hora</span><input type="number" id="cf-reunioes" min="1" max="30" value="${c.limites_sessao.reunioes_por_hora}"></label><label class="toggle"><span>Rodadas máximas do Conselho (1–5)</span><input type="number" id="cf-rodadas" min="1" max="5" value="${c.rodadas_maximas}"></label><div class="acoes"><button id="cf-salvar" class="btn">Salvar</button></div><p class="mini dim" style="margin:6px 0 0">Pasta: ${esc(r.home)} · banco: ${esc(r.banco)}</p>`;
    $("cf-salvar").addEventListener("click", async () => { try { await post("/api/config", { coleta_automatica: $("cf-coleta").checked, intervalo_coleta_segundos: Number($("cf-intervalo").value), rodadas_maximas: Number($("cf-rodadas").value), limites_sessao: { chamadas_ia_por_sessao: Number($("cf-limite").value), reunioes_por_hora: Number($("cf-reunioes").value) } }); toast("Configuração salva."); carregarConfig(); } catch (e) { toast(e.message); } });
  } catch (e) { $("sis-config").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
}
async function carregarCotas() {
  try { const r = await api("/api/cotas"); const p = r.cotas.provedores;
    $("sis-cotas").innerHTML = `<p class="peq muted" style="margin:0 0 6px">Chamadas nesta sessão: ${r.cotas.chamadas_sessao}/${r.cotas.limite_sessao}</p><div class="rolagem"><table class="tabela"><thead><tr><th>Provedor</th><th>Hoje</th><th>/min</th><th>OK</th><th>Erros</th><th>Estado</th></tr></thead><tbody>${Object.entries(p).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.hoje}/${v.limites.rpd}</td><td>${v.ultimo_minuto}/${v.limites.rpm}</td><td>${v.chamadas_ok}</td><td>${v.chamadas_erro}</td><td>${esc(v.desativado || v.motivo_cooldown || "ok")}</td></tr>`).join("") || '<tr><td colspan="6">Nenhuma chamada ainda.</td></tr>'}</tbody></table></div>${r.uso_24h.length ? `<p class="mini dim" style="margin:6px 0 0">24 h: ${r.uso_24h.map((u) => esc(u.provedor) + " " + u.chamadas + " chamadas (" + u.falhas + " falhas, ~" + fmtInt(u.tokens_entrada) + " tokens de entrada)").join(" · ")}</p>` : ""}`;
  } catch (e) { $("sis-cotas").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
}
async function testarTudo() {
  $("sis-testar").disabled = true; $("sis-diag").innerHTML = '<div class="vazio"><span class="spin"></span> Testando servidor, TSE, banco e cada provedor (até 60 s)…</div>';
  try {
    const d = await api("/api/diagnostico", {}, 90000); ultimoDiag = d; $("sis-versao").textContent = "v" + d.versao;
    const linha = (k, ok, txt) => `<div class="item"><span class="tipo ${ok === true ? "fato" : ok === false ? "limitacao" : "calculo"}">${ok === true ? "ok" : ok === false ? "falha" : "info"}</span><div><b>${esc(k)}</b><p>${esc(txt)}</p></div></div>`;
    let html = linha("Servidor", true, `ativo · Python ${d.servidor.python} · ${d.servidor.termux ? "Termux" : d.servidor.plataforma} · ${d.servidor.bind}:${d.servidor.porta}`);
    html += linha("TSE", d.tse.ok, d.tse.mensagem + (d.tse.ok ? ` · boletim ${d.tse.horario_tse} · ${fmtPct(d.tse.secoes_pct)}% seções · ${d.tse.atualidade.rotulo}` : d.tse.http ? ` (HTTP ${d.tse.http})` : ""));
    html += linha("Códigos de eleição", d.eleicoes.verificacao.ok, `presidente 1T ${d.eleicoes.codigos.presidente.turno1} / 2T ${d.eleicoes.codigos.presidente.turno2} · governador 2T ${d.eleicoes.codigos.governador.turno2} · ${d.eleicoes.verificacao.mensagem}${d.eleicoes.verificacao.divergencias.length ? " · " + d.eleicoes.verificacao.divergencias.join(" ") : ""}`);
    html += linha("Banco", d.banco.ok, d.banco.ok ? `funcional · ${d.banco.snapshots} snapshots guardados · ${esc(d.banco.caminho)}` : d.banco.erro);
    html += linha("Segredos", d.segredos.permissoes_ok, `${d.segredos.configurados.length ? d.segredos.configurados.join(", ") : "nenhuma chave"} · arquivo ${d.segredos.permissoes_ok ? "com permissão restrita" : "COM PERMISSÕES ABERTAS: rode chmod 600"}`);
    for (const p of d.provedores) html += linha(p.nome, p.configurado ? p.autenticado : null, (p.configurado ? p.mensagem : "sem chave") + (p.modelo ? " · modelo: " + p.modelo : "") + (p.pronto ? " · PRONTO" : ""));
    html += linha("Conselho", d.conselho.modelos_prontos > 0, `${d.conselho.modelos_prontos} modelo(s) realmente prontos de ${d.conselho.provedores_distintos} provedor(es)` + (d.conselho.cadeiras.length ? ": " + d.conselho.cadeiras.map((c) => c.papel_nome + " → " + c.provedor_nome).join("; ") : ""));
    html += linha("Coletor", d.coletor.ativo, `${d.coletor.ativo ? "ativo" : "parado"} · ${d.coletor.consultas} consultas · ${d.coletor.boletins_novos} boletins novos · ${d.coletor.repetidos} repetidos · ${d.coletor.erros} erros${d.coletor.ultimo_erro ? " · " + d.coletor.ultimo_erro : ""} · governadores: ${(d.coletor.governador_ufs || []).join(", ").toUpperCase()}${d.coletor.governador_verificado ? " (confirmados)" : " (padrão)"}`);
    html += linha("Última atualização", null, `${d.ultima_atualizacao.horario_tse_br || "—"} · ${(d.ultima_atualizacao.atualidade || {}).rotulo || ""}`);
    $("sis-diag").innerHTML = html; await carregarProvedores();
  } catch (e) { $("sis-diag").innerHTML = `<div class="erro">${esc(e.message)}</div>`; } finally { $("sis-testar").disabled = false; }
}
async function copiarDiag() {
  if (!ultimoDiag) { toast("Rode Testar tudo primeiro."); return; }
  const t = ultimoDiag.texto || "";
  try { await navigator.clipboard.writeText(t); toast("Diagnóstico copiado (sem chaves)."); } catch (e) { window.prompt("Copie o diagnóstico:", t); }
}

/* ------------------------------------------------------------ navegação */
function mudarAba(k) {
  estado.aba = k; guardar("aba", k);
  document.querySelectorAll(".aba").forEach((a) => a.classList.toggle("ativa", a.id === "aba-" + k));
  document.querySelectorAll(".rodape [data-aba]").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === k));
  window.scrollTo({ top: 0 });
  if (k === "estados") carregarEstados();
  if (k === "historico") carregarHistorico();
  if (k === "analista") renderAnalista();
  if (k === "conselho") carregarConselho();
  if (k === "sistema") carregarSistema();
}
document.querySelectorAll(".rodape [data-aba]").forEach((b) => b.addEventListener("click", () => mudarAba(b.dataset.aba)));
$("btn-atualizar").addEventListener("click", () => atualizar(true));
$("sel-escopo").addEventListener("change", (e) => { estado.escopo = e.target.value; guardar("escopo", estado.escopo); montarEscopos(); carregarResultado().then(() => { renderPainel(); if (estado.aba === "historico") carregarHistorico(); }); });
$("sel-cargo").addEventListener("change", (e) => { estado.cargo = e.target.value; guardar("cargo", estado.cargo); carregarResultado().then(() => { renderPainel(); if (estado.aba === "historico") carregarHistorico(); }); });
document.addEventListener("visibilitychange", () => { if (!document.hidden && Date.now() >= estado.proximo) atualizar(); });
window.addEventListener("online", () => atualizar());
setInterval(() => {
  if (document.hidden) return;
  if (!estado.carregando && Date.now() >= estado.proximo) atualizar(); else contagem();
  if (estado.aba === "conselho" && estado.autoConselho && estado.conselhoStatus && estado.conselhoStatus.modelos_prontos > 0 && !estado.reuniaoEmCurso) {
    const assin = estado.escopo + "|" + ((estado.resultado || {}).horario_tse || "");
    if (Date.now() - (estado.ultimaReuniao || 0) >= 600000 && assin !== estado.assinaturaReuniao && (estado.resultado || {}).ok && !$("co-convocar").disabled) convocar();
  }
}, 1000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
mudarAba(estado.aba);
atualizar();
})();
