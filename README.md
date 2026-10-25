# Radar 2026 + O Conselho

Aplicativo de análise eleitoral que roda **no próprio Samsung Galaxy S23** (Termux + Chrome):
acompanha a totalização oficial do TSE do **2º turno de 25/10/2026**, calcula tudo com um motor
matemático determinístico e, se você fornecer suas chaves gratuitas, convoca **O Conselho** — vários
modelos de linguagem que analisam os mesmos boletins de forma independente, se confrontam, replicam,
passam por uma auditoria numérica e recebem um relatório com concordâncias e divergências.

Nenhum voto, pesquisa ou horário é inventado. Nenhuma probabilidade de vitória é estimada. Nenhum
serviço pago é ativado. As chaves ficam só no seu aparelho.

> Projeto independente, sem vínculo com o Tribunal Superior Eleitoral.

## Instalar no S23 (um comando)

1. Instale o **Termux** pelo F-Droid (a versão da Play Store é antiga).
2. Abra o Termux e cole:

```bash
curl -fsSL https://raw.githubusercontent.com/Fliparaujor/apuracao-2026/main/instalar.sh | bash
```

Enquanto esta versão ainda não estiver no branch `main`, use o branch de desenvolvimento:

```bash
curl -fsSL https://raw.githubusercontent.com/Fliparaujor/apuracao-2026/claude/blissful-fermi-9oy396/instalar.sh | RADAR_BRANCH=claude/blissful-fermi-9oy396 bash
```

O instalador instala Python e Git, baixa o projeto em `~/apuracao-2026`, verifica o ambiente,
pergunta se você quer configurar chaves de IA (pode pular) e inicia o servidor.

3. Abra no Chrome: **http://127.0.0.1:8080/** → menu ⋮ → **Instalar app** (fica na tela inicial).

### Dia a dia

```bash
cd ~/apuracao-2026
bash radar.sh            # inicia o servidor (Ctrl+C encerra; o histórico fica guardado)
bash radar.sh chaves     # adicionar, trocar, remover ou testar chaves de IA
bash radar.sh diagnostico
bash radar.sh atualizar  # git pull
bash radar.sh testes
```

O Termux precisa permanecer aberto. O `radar.sh` aciona `termux-wake-lock`; mesmo assim, veja
[Limitações no Android](#limitações-no-android).

## Configurar as chaves (sem editar arquivo nenhum)

`bash radar.sh chaves` abre um assistente que pergunta provedor por provedor. Você cola a chave
**no Termux** (não aparece ao digitar), o programa testa a autenticação e lista os modelos que a sua
conta realmente pode usar, e grava em `~/.radar2026/segredos.env` com permissão `600`, fora do Git.
Chave inválida é apontada com o HTTP devolvido e pode ser removida na hora. Nunca cole chaves em
chats, prints ou mensagens; se expôs uma, revogue-a no site do provedor.

| Provedor | Variável | Onde criar | Nível gratuito (resumo) |
| --- | --- | --- | --- |
| Groq | `GROQ_API_KEY` | console.groq.com/keys | sem cartão; ~30 req/min, cota diária; catálogo muda |
| Gemini (AI Studio) | `GEMINI_API_KEY` | aistudio.google.com/api-keys | free tier com cotas baixas; modelos Pro podem não estar disponíveis |
| Mistral | `MISTRAL_API_KEY` | console.mistral.ai/api-keys | plano gratuito, pede verificação de telefone |
| OpenRouter | `OPENROUTER_API_KEY` | openrouter.ai/settings/keys | só modelos `:free`; dezenas de req/dia sem crédito |
| Cohere | `COHERE_API_KEY` | dashboard.cohere.com/api-keys | chave trial, 1.000 chamadas/mês, uso não comercial |
| Cloudflare Workers AI | `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` | dash.cloudflare.com | 10.000 Neurons/dia no plano Free (excesso é negado, não cobrado) |
| Hugging Face | `HF_TOKEN` | huggingface.co/settings/tokens | crédito mensal mínimo; para em HTTP 402 |

Os modelos **não são fixos no código**: cada adaptador lista o catálogo da conta e escolhe por
preferência (por exemplo, no Groq `openai/gpt-oss-120b` → `qwen/…` → `llama…`; no Gemini o
`flash` estável mais novo, depois `flash-lite`). O modelo realmente usado aparece na interface.
Para forçar um modelo, edite `modelos_preferidos` em `~/.radar2026/config.json` ou use a aba Sistema.

**Aviso honesto:** os limites gratuitos acima vêm da documentação e de relatos de outubro/2026 e
mudam sem aviso. O app trata HTTP 401/402/403/404/429/5xx, respeita `Retry-After`, pausa o provedor
após falhas seguidas e nunca ativa cobrança. Uma assinatura de chatbot (ChatGPT, Gemini app, Le Chat)
**não** vale como chave de API.

## O que o app faz

**Painel** — Presidente (Brasil, 27 UFs, Fortaleza, Macapá e qualquer município pelo código do TSE)
e Governador nas UFs com 2º turno (lista confirmada em tempo de execução contra os arquivos do TSE).
Percentuais, votos, diferença em votos e pontos, seções totalizadas, comparecimento, brancos/nulos,
status oficial, variação desde o boletim anterior e cenário hipotético com premissa explícita.

**Estados** — comparação regional, ordenação por nome, totalização ou margem, dispersão da totalização
e alertas de UFs atrasadas.

**Histórico** — evolução por boletim (gráfico), tabela de boletins e contadores que separam
*consultas ao TSE* de *boletins realmente novos*.

**Analista** — perguntas livres a um modelo, sempre com a leitura matemática ao lado e auditoria dos
números citados. Sem chave, responde só com a matemática.

**O Conselho** — ver abaixo.

**Sistema** — "Testar tudo": servidor, TSE, códigos de eleição, banco, segredos, cada provedor
(configurado / autenticado / modelo / pronto), coletor, última atualização e cotas; resultado
copiável sem segredos. Configuração de intervalo, limites de sessão e rodadas.

### Selo de atualidade

`AO VIVO` só aparece quando o boletim do TSE tem até 15 minutos e a totalização não foi encerrada.
Caso contrário: `Boletim há N min`, `Totalização encerrada` ou `Dados históricos`. Se o servidor
local cair, a interface mostra o último estado guardado **rotulado como guardado**, nunca como ao vivo.

## O Conselho

Cadeiras (papéis) atribuídas aos modelos prontos, com diversidade de provedor antes de repetir
provedor; modelos do mesmo provedor são marcados como **não independentes**:

Quantitativo · Cético · Regional · Histórico · Metodologia · Investigativo · Auditor ·
Participação · Ritmo · Relator (o relator é a primeira cadeira, ou uma cadeira dedicada com 8+ modelos).

Protocolo de uma reunião:

1. **Pareceres independentes** — cada modelo recebe só a evidência oficial, o histórico necessário,
   a pergunta, as instruções do papel e as regras de neutralidade. Ninguém vê os outros.
2. **Confronto** — cada modelo recebe os pareceres alheios e aponta concordâncias verificáveis,
   afirmações sem suporte, premissas, inconsistências, explicações alternativas e dados necessários.
3. **Réplicas** — curtas; puladas automaticamente quando a cota está curta.
4. **Auditoria determinística** — todo número citado é conferido contra os arquivos do TSE e os
   cálculos do motor; prognósticos ("vai vencer", "% de chance") são marcados.
5. **Relatório** — fatos confirmados, cálculos, concordâncias (quantos e quais), divergências
   persistentes, hipóteses a verificar, limitações, fontes e horários.

Classificação honesta do resultado: **deliberação** (2+ modelos), **análise individual** (1 modelo),
**debate sem relatoria** (relator falhou → síntese automática sem IA) ou **somente matemática**
(nenhum modelo). Falha de um provedor nunca derruba os outros. A reunião roda em segundo plano com
progresso por rodada e botão de cancelar. Há limite de reuniões por hora e de chamadas por sessão;
a reconvocação automática a cada boletim novo é **opcional e desligada por padrão**.

## Dados oficiais

Fonte: `https://resultados.tse.jus.br/oficial/ele2026/<eleição>/dados/<uf>/<uf><município>-c<cargo>-e<eleição>-u.json`
(arquivo de resultado unificado, EA20). Códigos: **6257** (1º turno federal, 04/10), **6258**
(2º turno federal), **6260** (2º turno estadual). O servidor lê `comum/config/ele-c.json` na
inicialização e registra qualquer divergência. O coletor consulta os escopos prioritários a cada
30 s e os demais estados a cada 60 s, guardando em SQLite (`~/.radar2026/radar.sqlite3`) **apenas
boletins diferentes** — uma resposta HTTP 200 repetida não vira boletim novo. O 1º turno é
guardado como referência histórica e comparado com as ressalvas metodológicas devidas.

Campos interpretados: `carg/agr/par/cand` (`n`, `nmu`, `nm`, `vap`, `pvap`/`pvapn`, `st`, `e`,
`sqcand`), `s.pst/pstn/st/ts`, `v.vv/vb/tvn/pvb/ptvn`, `e.te/est/c/a/pc/pa`, `dt/ht`, `dg/hg`, `tf`,
`md`, `cdabr`, `t`, `ele`.

## Limitações no Android

- O Android pode suspender o Termux em segundo plano (economia de bateria, "phantom process killer").
  Mantenha o Termux aberto ou na notificação persistente, desative a otimização de bateria para o
  Termux e, no Android 14+, considere a opção de desenvolvedor "Desativar restrições de processos
  filhos". O app **não** alega coleta ininterrupta: o histórico cobre apenas os períodos em que o
  servidor esteve ativo, e os contadores mostram isso.
- A coleta do TSE continua funcionando mesmo com todas as IAs esgotadas ou sem chave.
- O servidor escuta em `127.0.0.1`. Para expor na rede (`RADAR_BIND=0.0.0.0`) defina também
  `RADAR_TOKEN` e coloque um proxy HTTPS na frente; as chaves nunca saem do backend.

## O que foi e o que não foi validado

Validado neste repositório (CI em GitHub Actions, Python 3.11–3.13):

- 66 testes: parser TSE com os campos reais de 2026, banco (dedupe, migração, importação do banco
  antigo), motor matemático, cotas, os 7 adaptadores com HTTP simulado, O Conselho completo com
  respostas **simuladas** (5 rodadas, falha de modelo, 1 modelo, 0 modelos, cancelamento, auditoria
  pegando número inventado), API local real, segurança (nenhum segredo em respostas, logs ou repositório);
- interface no viewport do S23 (Playwright): 6 abas sem transbordamento, botões acessíveis, diagnóstico sem segredos.

**Não validado aqui, por falta de acesso de rede do ambiente de desenvolvimento ao TSE e às APIs
dos provedores:** as chamadas reais ao TSE e a cada provedor. Os formatos seguem a documentação e
coletores públicos que gravaram os arquivos reais de 25/10/2026; a primeira execução no S23 com
`bash radar.sh diagnostico` e **Sistema → Testar tudo** é o teste real. Se um provedor devolver
algo inesperado, ele aparece como "não pronto" com o HTTP e a mensagem, sem derrubar o restante.

## Estrutura

```
radar/            backend (stdlib apenas)
  tse.py          camada 1 · coleta oficial        db.py          camada 2 · SQLite
  matematica.py   camada 3 · motor determinístico  provedores/    camada 4 · 7 adaptadores + cotas.py
  conselho.py     camada 5 · deliberação           servidor.py    camada 6 · API + estáticos
  diagnostico.py  camada 7 · "Testar tudo"         coletor.py     coleta em segundo plano
  analista.py, evidencias.py, jobs.py, config.py, configurador.py, __main__.py
web/              interface PWA (index.html, app.js, app.css, sw.js, manifest, ícones)
tests/            testes + TSE simulado + provedores simulados + teste de UI
radar.sh, instalar.sh, server.py (compatibilidade: `python server.py`)
legado/primeiro-turno.html  versão anterior preservada
```

Licença e responsabilidade: uso pessoal e educativo; confirme sempre no TSE antes de divulgar números.
