(() => {
"use strict";
const $=id=>document.getElementById(id);
const css=document.createElement("style");
css.textContent=".council-members{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.council-member{padding:12px;background:#101e31;border:1px solid #334861;border-radius:12px;min-width:0}.council-member b{display:block;font-size:13px}.council-member span{font-size:11px;color:var(--muted);display:block}.council-member em{font-size:11px;color:#8ce1b9;font-style:normal;font-weight:800}.council-member em.off{color:#e5bd83}.council-member a{font-size:11px}.council-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:13px 0}.council-stats div{border:1px solid #2c405c;background:#0d1929;border-radius:10px;padding:11px;text-align:center}.council-stats strong{display:block;font-size:23px}.council-stats small{display:block;font-size:10px;color:var(--muted)}.council-question{display:block;min-height:88px;width:100%;background:#0b1726;border:1px solid #435873;border-radius:12px;padding:12px;font:inherit;color:var(--text);resize:vertical}.council-button{background:#b3d6ff;color:#091626;border:0;border-radius:12px;padding:13px 16px;font-weight:900}.council-button:disabled{opacity:.45}.council-check{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}.council-check input{accent-color:#a0caff;width:16px;height:16px}.council-card{padding:13px;margin:9px 0;background:#101e30;border:1px solid #2c4160;border-radius:12px}.council-card .head{display:flex;justify-content:space-between;gap:9px}.council-card .head strong{font-size:13px}.council-card .head span{font-size:11px;text-align:right;color:var(--muted)}.council-text{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.67;margin-top:10px}.council-summary{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.75;font-size:14px}.council-meta{font-size:11px;line-height:1.55;color:var(--muted);overflow-wrap:anywhere;margin-top:10px}.council-title{font-size:27px;letter-spacing:-1px;font-weight:900}.council-note{background:#2c251a;border:1px solid #5f4c34;border-radius:11px;padding:12px;color:#f4d4a4;font-size:12px}.council-spin{display:inline-block;width:16px;height:16px;border:2px solid #466484;border-top-color:#f3f7ff;border-radius:50%;animation:spin 1s linear infinite;vertical-align:-3px;margin-right:5px}.council-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.7px;font-weight:800;margin:14px 0 8px}.bottomnav button{width:min(16.66%,130px);font-size:10px}@media(min-width:700px){.council-members{grid-template-columns:repeat(3,minmax(0,1fr))}}";
document.head.appendChild(css);
const view=document.createElement("div");view.className="view";view.id="council";
view.innerHTML=[
'<section class="card"><div class="card-head"><div><div class="council-title">◈ O Conselho</div><div class="muted" style="font-size:12px">IAs debatem. Evidências decidem.</div></div><span class="pill">Multi-IA</span></div>',
'<p class="muted" style="font-size:13px">Cada IA analisa os mesmos arquivos oficiais do TSE sem conhecer a resposta das outras. Depois elas apontam erros e hipóteses rivais; um relator registra onde concordam e onde discordam.</p>',
'<div class="council-stats"><div><strong id="c-count">—</strong><small>modelos ativados</small></div><div><strong id="c-providers">—</strong><small>provedores distintos</small></div><div><strong>3</strong><small>rodadas</small></div></div>',
'<div id="c-note" class="council-note">Para convocar, configure uma chave Groq gratuita no Termux. Modelos sem chave não podem participar.</div>',
'<div class="council-label">Conselheiros</div><div class="council-members" id="c-members">Verificando as cadeiras…</div>',
'<div class="council-label">Pergunta ao Conselho</div><textarea id="c-question" maxlength="360" class="council-question" placeholder="O que está mudando na apuração? Quais explicações alternativas existem?"></textarea>',
'<div class="row" style="justify-content:space-between;align-items:center;margin:14px 0 8px">',
'<button class="council-button" id="c-run" disabled>◈ Convocar Conselho</button>',
'<label class="council-check"><input id="c-auto" type="checkbox"> Automático a cada 10 min*</label></div>',
'<p class="council-meta">* Só com esta aba aberta, parcial nova, servidor ligado e cota gratuita disponível. Uma reunião pode exigir duas chamadas por IA e uma para a relatoria. Não produz previsões eleitorais.</p>',
'<div id="c-progress" class="council-meta"></div></section>',
'<section class="card"><div class="card-head"><h2>Relatório do Conselho</h2><small id="c-scope">Brasil</small></div>',
'<div id="c-summary" class="council-summary">Nenhuma reunião realizada.</div><div id="c-meta" class="council-meta"></div><div id="c-warnings"></div></section>',
'<section class="card"><div class="card-head"><h2>O debate completo</h2><span class="pill">Transparência</span></div>',
'<div class="council-label">1 · Pareceres separados</div><div id="c-first" class="council-meta">As respostas aparecerão aqui.</div>',
'<div class="council-label">2 · Críticas cruzadas</div><div id="c-replies" class="council-meta">Réplicas após as análises iniciais.</div></section>'
].join("");
const method=$("method");method.parentElement.insertBefore(view,method);
const nav=document.querySelector(".bottomnav"),btn=document.createElement("button");
btn.dataset.tab="council";btn.innerHTML="<b>◈</b>Conselho";
nav.insertBefore(btn,nav.querySelector('[data-tab="method"]'));
const state={enabled:false,active:false,working:false,auto:false,last:0,lastSignature:""};
const local=()=>["127.0.0.1","localhost"].includes(location.hostname);
const area=()=>($("scope").selectedOptions[0]?.textContent||"Brasil").replace(" — total nacional","");
const signature=()=>($("scope").value||"br")+"|"+($("source-time").textContent||"");
function progress(message,loading){
  const el=$("c-progress");el.replaceChildren();
  if(loading){const sp=document.createElement("span");sp.className="council-spin";el.append(sp);}
  el.append(document.createTextNode(message));
}
function renderMembers(items){
  const list=$("c-members");list.replaceChildren();
  for(const m of items){
    const node=document.createElement("div");node.className="council-member";
    const title=document.createElement("b");title.textContent=m.name;
    const sub=document.createElement("span");sub.textContent=m.role+" · "+m.provider;
    const availability=document.createElement("em");
    availability.textContent=m.configured?"Com chave":"Sem chave";
    if(!m.configured)availability.className="off";
    node.append(title,sub,availability);
    if(!m.configured){const a=document.createElement("a");a.href=m.setup;a.rel="noopener";a.target="_blank";a.textContent="Criar chave grátis";node.append(document.createElement("br"),a);}
    list.append(node);
  }
}
async function status(){
  $("c-scope").textContent=area();
  if(!local()){
    progress("Esta função precisa do endereço local do Termux: http://127.0.0.1:8080/ao-vivo.html.");
    $("c-note").textContent="Não é seguro guardar chaves no site público. O Conselho só opera pelo servidor local.";
    return;
  }
  try{
    const r=await fetch("/api/conselho/status",{cache:"no-store"});
    if(!r.ok)throw Error("Atualize o servidor");
    const data=await r.json();renderMembers(data.members);
    $("c-count").textContent=data.active_members;$("c-providers").textContent=data.independent_providers;
    state.enabled=data.active_members>=2;$("c-run").disabled=!state.enabled||state.working;
    $("c-note").textContent=state.enabled
      ?"As cadeiras ativadas estão prontas. Múltiplos modelos do mesmo provedor não equivalem a fontes independentes."
      :"Configure GROQ_API_KEY no Termux: ela habilita duas IAs diferentes. Adicione chaves Mistral, OpenRouter, Cohere ou Gemini para maior diversidade.";
    progress(state.enabled?"Pronto para convocação. O debate consome parte da cota gratuita.":"Ainda não há pelo menos dois modelos com chave.");
  }catch(e){
    state.enabled=false;$("c-run").disabled=true;
    $("c-note").textContent="O Conselho ainda não está carregado no servidor: execute git pull e reinicie python server.py no Termux.";
    progress("Falha ao acessar /api/conselho/status.");
  }
}
function card(r){
  const node=document.createElement("article");node.className="council-card";
  const h=document.createElement("div");h.className="head";
  const t=document.createElement("strong");t.textContent=r.name||"Modelo";
  const sub=document.createElement("span");sub.textContent=(r.provider||"")+" · "+(r.role||r.model||"");
  h.append(t,sub);node.append(h);
  const text=document.createElement("div");text.className="council-text";
  text.textContent=r.ok?(r.text||"Sem resposta"):"Não participou: "+(r.error||"indisponível");
  node.append(text);return node;
}
function renderList(id,items){
  const box=$(id);box.replaceChildren();
  if(!items||!items.length){box.textContent="Nenhuma resposta registrada.";return;}
  for(const it of items)box.append(card(it));
}
function report(data){
  $("c-summary").textContent=data.sintese||data.error||"Não foi possível sintetizar o debate.";
  $("c-scope").textContent=area()+" · 2º turno";
  const meta=$("c-meta");meta.replaceChildren();
  meta.append(document.createTextNode("TSE "+(data.horario_tse||"—")+" · "+
    (data.conselheiros_validos||0)+" modelos responderam · "+
    (data.provedores_validos||0)+" provedores"+(data.relator?" · Relator: "+data.relator:"")));
  if(data.fonte){const a=document.createElement("a");a.href=data.fonte;a.target="_blank";a.rel="noopener";a.textContent=" · Ver JSON oficial do TSE";meta.append(a);}
  $("c-warnings").replaceChildren();
  for(const warn of data.avisos||[]){
    const w=document.createElement("p");w.className="council-meta";w.textContent="• "+warn;$("c-warnings").append(w);
  }
  renderList("c-first",data.membros);
  renderList("c-replies",data.replicas);
}
async function convene(){
  if(!state.enabled||state.working)return;
  state.working=true;state.last=Date.now();state.lastSignature=signature();$("c-run").disabled=true;
  progress("Análise separada → críticas cruzadas → síntese com divergências. O processo pode levar alguns minutos.",true);
  $("c-summary").textContent="Conselho em reunião; nenhuma conclusão emitida ainda.";
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),260000);
  try{
    const r=await fetch("/api/conselho/debater",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({scope:$("scope").value,question:$("c-question").value}),signal:controller.signal
    });
    const data=await r.json();if(!r.ok)throw Error(data.erro||("HTTP "+r.status));
    report(data);
    progress(data.status==="relatorio"?"Reunião concluída. Leia acordos, divergências e limites.":"Reunião parcialmente concluída: há modelos indisponíveis.");
  }catch(e){
    progress("Reunião não concluída.");
    $("c-summary").textContent="Falha no Conselho: "+(e.name==="AbortError"?"tempo limite excedido":e.message)+". O acompanhamento numérico segue disponível.";
  }finally{clearTimeout(timeout);state.working=false;$("c-run").disabled=!state.enabled;}
}
btn.addEventListener("click",()=>{
  state.active=true;
  document.querySelectorAll(".view").forEach(v=>v.classList.toggle("active",v.id==="council"));
  document.querySelectorAll(".bottomnav [data-tab]").forEach(b=>b.classList.toggle("active",b===btn));
  window.scrollTo(0,0);status();
});
nav.querySelectorAll("[data-tab]").forEach(b=>{if(b!==btn)b.addEventListener("click",()=>state.active=false);});
$("scope").addEventListener("change",()=>{$("c-scope").textContent=area()+" · 2º turno";});
$("c-run").addEventListener("click",convene);
$("c-auto").addEventListener("change",e=>{state.auto=e.target.checked;});
setInterval(()=>{
  if(!state.active||!state.auto||!state.enabled||state.working||document.hidden)return;
  if(Date.now()-state.last<600000||signature()===state.lastSignature)return;
  if($("source-time").textContent.includes("sem resposta válida"))return;
  convene();
},30000);
})();