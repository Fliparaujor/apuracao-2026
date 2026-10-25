(() => {
"use strict";
const $ = id => document.getElementById(id);
const style = document.createElement("style");
style.textContent = ".ai-copy{font-size:13px;color:var(--muted);line-height:1.6}.ai-label{display:block;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin:15px 0 6px}.ai-control{display:block;width:100%;padding:12px;background:#0d1929;color:var(--text);border:1px solid #3b526f;border-radius:11px;font:inherit}.ai-box{min-height:90px;resize:vertical}.ai-chips{display:flex;flex-wrap:wrap;gap:6px;margin:11px 0 16px}.ai-chips button{background:#203652;border:1px solid #3d5572;border-radius:20px;padding:7px 10px;color:#d1e5ff;font-size:11px;font-weight:700}.ai-submit{border:none;background:#87beff;color:#0a1420;padding:13px 17px;border-radius:11px;font-weight:900;font-size:13px}.ai-submit:disabled{opacity:.4}.ai-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.68;font-size:14px;color:var(--text)}.ai-meta{font-size:11px;line-height:1.55;color:var(--muted);overflow-wrap:anywhere;margin:12px 0}.ai-guide{background:#12253a;border:1px dashed #4a6383;border-radius:12px;padding:14px;font-size:12px;color:#c3d9f2}.ai-guide code{display:block;background:#0b1626;border-radius:8px;margin:10px 0;padding:11px;white-space:pre-wrap;overflow-wrap:anywhere;color:#a6eac3;font-size:12px}.ai-check{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:12px}.ai-check input{accent-color:#8cbdff;width:16px;height:16px}.bottomnav button{width:min(20%,185px)}";
document.head.appendChild(style);
const div=document.createElement("div");div.className="view";div.id="analyst";
div.innerHTML=[
'<section class="card"><div class="card-head"><h2>✦ Analista político com IA</h2><span id="ai-state" class="pill warn">Verificando</span></div>',
'<p class="ai-copy">Interpretação contextual dos resultados oficiais, diferenças regionais e histórico do primeiro turno. A IA diferencia fatos, cálculos e hipóteses; não produz probabilidades eleitorais.</p>',
'<div class="notice">Números oficiais do TSE; interpretação gerada pela IA via Groq Free ou Gemini, sujeita a erros. Os dados públicos e a pergunta serão enviados ao modelo. Consulte os boletins e horários.</div>',
'<div class="ai-guide" id="ai-guide" hidden><b>Para ativar a IA</b><p>Crie uma conta gratuita no GroqCloud (sem conta de faturamento) e gere uma chave na área API Keys. No Termux, encerre o servidor com Ctrl+C, depois execute:</p>',
'<code>cd ~/apuracao-2026\n',
'git pull\n',
'read -rsp "Cole sua chave Groq: " GROQ_API_KEY; echo\n',
'export GROQ_API_KEY\n',
'python server.py</code>',
'<p>A chave fica só nesta sessão do Termux. Não compartilhe com outras pessoas e não a coloque no GitHub.</p>',
'<a href="https://console.groq.com/keys" target="_blank" rel="noopener">Criar chave grátis no GroqCloud</a></div>',
'<label class="ai-label" for="ai-mode">Tipo de análise</label>',
'<select id="ai-mode" class="ai-control"><option value="resumo">Briefing — o que aconteceu?</option><option value="investigar">Investigação — estados e 1º turno</option><option value="cenarios">Cenários aritméticos sem previsão</option></select>',
'<label class="ai-label" for="ai-question">O que você quer investigar? (opcional)</label>',
'<textarea class="ai-control ai-box" maxlength="500" id="ai-question" placeholder="Ex.: O que mudou em Minas e no Nordeste? Existem explicações alternativas?"></textarea>',
'<div class="ai-chips">',
'<button data-question="O que mudou na apuração? Distinga fato, cálculo e lacuna dos dados.">O que mudou?</button>',
'<button data-question="Compare os dados oficiais de Ceará, Amapá e Brasil; considere estágios distintos de apuração.">CE × AP × Brasil</button>',
'<button data-question="Investigue padrões entre os estados e diferenças de velocidade da apuração, com hipóteses testáveis.">Analisar estados</button>',
'<button data-question="Calcule cenários condicionais com volumes hipotéticos de votos adicionais. Não preveja vitória.">Cenários</button>',
'</div>',
'<div class="row" style="align-items:center;justify-content:space-between"><button class="ai-submit" id="ai-submit">✦ Analisar agora</button><label class="ai-check"><input type="checkbox" id="ai-auto"> Auto a cada 3 min*</label></div>',
'<p class="ai-meta">* Somente com a aba aberta, dados novos e o Termux funcionando. Limites da API gratuita continuam valendo.</p>',
'</section>',
'<section class="card"><div class="card-head"><h2>Relatório do analista</h2><small id="ai-region">Brasil · 2º turno</small></div><div id="ai-output" class="ai-text">Conecte a IA e toque em “Analisar agora”.</div><div id="ai-source" class="ai-meta"></div></section>'
].join("");
const method=$("method");method.parentElement.insertBefore(div,method);
const nav=document.querySelector(".bottomnav");
const btn=document.createElement("button");btn.dataset.tab="analyst";btn.innerHTML="<b>✦</b>Analista";
nav.insertBefore(btn,nav.querySelector('[data-tab="method"]'));
const state={configured:false,working:false,active:false,auto:false,last:0,lastSignature:""};
const local=()=>["localhost","127.0.0.1"].includes(location.hostname);
const region=()=>$("scope").value;
const label=()=>$("scope").selectedOptions[0]?.textContent||"Brasil";
const signature=()=>region()+"|"+($("source-time")?.textContent||"");
const regionLabel=()=>{$("ai-region").textContent=label()+" · Presidente · 2º turno";};
function statusLine(message,ok){$("ai-state").textContent=message;$("ai-state").className="pill "+(ok?"ok":"warn");}
async function status(){
  regionLabel();
  if(!local()){
    $("ai-guide").hidden=false;$("ai-submit").disabled=true;
    statusLine("Somente localhost",false);
    $("ai-output").textContent="Abra o painel pelo endereço http://127.0.0.1:8080/ao-vivo.html para usar o analista com a chave protegida no Termux.";
    return;
  }
  try{
    const c=new AbortController(),t=setTimeout(()=>c.abort(),7500);
    let response;try{response=await fetch("/api/ia/status",{cache:"no-store",signal:c.signal});}finally{clearTimeout(t);}
    if(!response.ok)throw Error("Servidor antigo");
    const data=await response.json();state.configured=!!data.configurada;
    statusLine(state.configured?("IA · "+data.modelo):"Sem chave",state.configured);
    $("ai-guide").hidden=state.configured;$("ai-submit").disabled=!state.configured;
    if(!state.last)$("ai-output").textContent=state.configured?"IA conectada. Faça sua pergunta e pressione Analisar agora.":"Configure a chave Groq gratuita com as instruções acima. O painel do TSE continua operando mesmo sem a IA.";
  }catch(e){
    state.configured=false;$("ai-guide").hidden=false;$("ai-submit").disabled=true;
    statusLine("Atualize o Termux",false);
    $("ai-output").textContent="Atualize o repositório com git pull, configure a chave e reinicie python server.py.";
  }
}
async function analyze(){
  if(!state.configured||state.working)return;
  state.working=true;state.last=Date.now();state.lastSignature=signature();
  $("ai-submit").disabled=true;statusLine("Analisando…",false);
  $("ai-output").textContent="Consultando TSE e primeiro turno, comparando regiões e produzindo a interpretação da IA…";
  $("ai-source").textContent="";
  const control=new AbortController(),timeout=setTimeout(()=>control.abort(),100000);
  try{
    const resp=await fetch("/api/ia/analisar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:region(),mode:$("ai-mode").value,question:$("ai-question").value}),signal:control.signal});
    const data=await resp.json();if(!resp.ok)throw Error(data.erro||("HTTP "+resp.status));
    $("ai-output").textContent=data.analise;
    $("ai-source").textContent="TSE: "+data.horario_tse+" · "+data.fonte_principal+" · UFs consultadas: "+data.total_ufs_consultadas+" · Modelo: "+data.modelo+" · "+data.aviso;
    statusLine("Análise concluída",true);
  }catch(e){
    $("ai-output").textContent="Não foi possível concluir a análise: "+(e.name==="AbortError"?"tempo limite excedido":e.message)+". A apuração numérica permanece independente da IA.";
    statusLine("Falha na IA",false);
  }finally{clearTimeout(timeout);state.working=false;$("ai-submit").disabled=!state.configured;}
}
btn.addEventListener("click",()=>{
  state.active=true;
  document.querySelectorAll(".view").forEach(v=>v.classList.toggle("active",v.id==="analyst"));
  document.querySelectorAll(".bottomnav [data-tab]").forEach(b=>b.classList.toggle("active",b===btn));
  window.scrollTo(0,0);
  status();
});
nav.querySelectorAll("[data-tab]").forEach(b=>{if(b!==btn)b.addEventListener("click",()=>state.active=false)});
$("scope").addEventListener("change",regionLabel);
$("ai-submit").addEventListener("click",analyze);
$("ai-auto").addEventListener("change",e=>state.auto=e.target.checked);
document.querySelectorAll("[data-question]").forEach(b=>b.addEventListener("click",()=>{
  $("ai-question").value=b.dataset.question;
  if(b.dataset.question.startsWith("Calcule"))$("ai-mode").value="cenarios";
  else if(b.dataset.question.startsWith("Investigue"))$("ai-mode").value="investigar";
}));
setInterval(()=>{
  if(!state.active||!document.getElementById("analyst").classList.contains("active")||!state.auto||!state.configured||state.working||document.hidden)return;
  if(Date.now()-state.last<180000||signature()===state.lastSignature)return;
  if(($("source-time")?.textContent||"").includes("sem resposta válida"))return;
  analyze();
},30000);
regionLabel();
})();