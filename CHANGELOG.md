# Histórico de alterações

## 3.0.0 — 25/10/2026 · Radar 2026 + O Conselho

Reescrita consolidada em arquitetura modular (`radar/`). Tudo o que existia em arquivos soltos
(`server.py`, `inteligencia.py`, `conselho.py`, `groq_provider.py`, `relatorio_local.py`,
`ao-vivo.html`, `analista.js`, `conselho.js`, `diagnostico.html`) foi substituído.

### Correções da auditoria
- "Chave presente" era tratada como "autenticada": agora há quatro estados distintos
  (configurado → autenticado → modelo disponível → pronto/participante), todos verificados
  por chamadas reais ao provedor.
- Modelos fixos e possivelmente inexistentes: cada adaptador descobre o catálogo da conta em
  tempo de execução e escolhe o modelo por preferência; nada é assumido.
- Cabeçalho indevido `cf-aig-gateway-id` na Cloudflare removido; validação do ID da conta.
- OpenRouter: roteador `openrouter/free` substituído por modelos `:free` concretos com
  `allow_fallbacks: false`; resposta roteada para modelo pago é descartada.
- HTTP 400 "API key not valid" (Gemini) agora é classificado como chave inválida, não erro de formato.
- Histórico guardado apenas no navegador: agora em SQLite no servidor, com deduplicação por
  assinatura (horário TSE + seções + válidos + votos por candidato) e contadores que separam
  consultas repetidas de boletins novos.
- Rótulo "AO VIVO" só com boletim de até 15 min e totalização não encerrada; caso contrário
  "Último boletim há N min", "Totalização encerrada" ou "Dados históricos".
- Snapshot incompleto: agora guarda horário TSE (`dt/ht` e `dg/hg`), seções, válidos, brancos,
  nulos, comparecimento, abstenção, eleitorado das seções totalizadas, status oficial e todos os
  candidatos.
- Sem gerenciador de cotas: criado `radar/cotas.py` (RPM/RPD/TPM, cooldown por 429, desativação
  automática por 401/402/403, limite por sessão, fila, cancelamento).
- Exposição de erros internos: mensagens mascaradas (valores de chaves e padrões conhecidos).

### Novidades
- Motor matemático determinístico (`radar/matematica.py`) com itens classificados em
  fato / cálculo / hipótese / limitação, variação entre boletins, trocas de liderança, variação
  regional, comparação com o 1º turno, cenários com premissa explícita e auditoria numérica de textos.
- O Conselho com protocolo de 5 rodadas (pareceres independentes, confronto, réplicas,
  auditoria determinística, relatório), papéis configuráveis, classificação honesta do resultado
  (deliberação / análise individual / somente matemática) e execução assíncrona com progresso e cancelamento.
- Analista com perguntas livres, contexto de sessão e fallback sem IA.
- Coletor em segundo plano (30 s; estados a cada 60 s) com recuo em falhas.
- Diagnóstico "Testar tudo" com texto copiável sem segredos.
- Interface mobile-first com 6 abas (Painel, Estados, Histórico, Analista, Conselho, Sistema), PWA
  com cache versionado só de arquivos estáticos e ícones gerados.
- Configurador interativo (`bash radar.sh chaves`), instalador de um comando (`instalar.sh`),
  segredos em `~/.radar2026/segredos.env` com permissão 600.
- Descoberta dos códigos de eleição em `ele-c.json` e das UFs com 2º turno para governador.
- 66 testes automatizados (parser TSE, banco e migração, matemática, cotas, provedores simulados,
  Conselho com falhas, API local, segurança) + teste de interface no viewport do Galaxy S23.

### Preservado
- `legado/primeiro-turno.html`: painel estático do 1º turno (versão anterior do `index.html`).
